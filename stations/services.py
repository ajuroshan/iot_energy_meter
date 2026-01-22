"""
Business logic for charging station operations.
"""

import logging
from decimal import Decimal

from django.db import transaction

from credits.models import CreditTransaction

from .models import ChargingSession, ChargingStation

logger = logging.getLogger(__name__)


class ChargingError(Exception):
    """Custom exception for charging-related errors."""

    pass


class ChargingService:
    """Service class for managing charging sessions."""

    @staticmethod
    @transaction.atomic
    def start_session(user, station: ChargingStation) -> ChargingSession:
        """
        Start a new charging session.

        Args:
            user: The user starting the session
            station: The charging station to use

        Returns:
            ChargingSession: The newly created session

        Raises:
            ChargingError: If session cannot be started
        """
        # Validate user has balance
        profile = user.profile
        if profile.balance_kwh <= 0:
            raise ChargingError("Insufficient balance. Please add credits to start charging.")

        # Validate station is available
        if not station.is_active:
            raise ChargingError("This station is not active.")

        if station.is_occupied:
            raise ChargingError("This station is currently in use.")

        if station.status == ChargingStation.StationStatus.OFFLINE:
            raise ChargingError("This station is offline.")

        # Check user doesn't have an active session elsewhere
        existing_session = ChargingSession.objects.filter(
            user=user, status=ChargingSession.SessionStatus.ACTIVE
        ).first()
        if existing_session:
            raise ChargingError(f"You already have an active session at {existing_session.station.name}.")

        # Create session
        session = ChargingSession.objects.create(
            user=user,
            station=station,
            start_energy_kwh=station.current_energy,
            status=ChargingSession.SessionStatus.ACTIVE,
        )

        # Mark station as occupied
        station.is_occupied = True
        station.save(update_fields=["is_occupied", "updated_at"])

        logger.info(f"Started charging session {session.id} for user {user.username} at station {station.name}")

        return session

    @staticmethod
    @transaction.atomic
    def stop_session(session: ChargingSession, current_energy_kwh: Decimal = None) -> ChargingSession:
        """
        Stop an active charging session and deduct credits.

        Args:
            session: The session to stop
            current_energy_kwh: Current energy reading (if None, uses station's current reading)

        Returns:
            ChargingSession: The updated session

        Raises:
            ChargingError: If session cannot be stopped
        """
        if session.status != ChargingSession.SessionStatus.ACTIVE:
            raise ChargingError("Session is not active.")

        # Get current energy reading
        if current_energy_kwh is None:
            current_energy_kwh = session.station.current_energy

        # Calculate consumed energy
        energy_consumed = session.calculate_energy_consumed(current_energy_kwh)

        # End the session
        session.end_session(current_energy_kwh, ChargingSession.SessionStatus.COMPLETED)

        # Deduct from user balance
        profile = session.user.profile
        profile.deduct_balance(energy_consumed)

        # Create transaction record
        CreditTransaction.objects.create(
            user=session.user,
            amount_kwh=-energy_consumed,
            transaction_type=CreditTransaction.TransactionType.SESSION_DEBIT,
            session=session,
            description=f"Charging session at {session.station.name}",
        )

        logger.info(
            f"Stopped session {session.id}: consumed {energy_consumed} kWh, new balance: {profile.balance_kwh} kWh"
        )

        return session

    @staticmethod
    @transaction.atomic
    def stop_session_no_credit(session: ChargingSession, current_energy_kwh: Decimal) -> ChargingSession:
        """
        Stop session due to insufficient credits.

        Args:
            session: The session to stop
            current_energy_kwh: Current energy reading

        Returns:
            ChargingSession: The updated session
        """
        energy_consumed = session.calculate_energy_consumed(current_energy_kwh)

        # End the session with special status
        session.end_session(current_energy_kwh, ChargingSession.SessionStatus.STOPPED_NO_CREDIT)
        session.notes = "Session stopped automatically due to insufficient credits."
        session.save(update_fields=["notes"])

        # Deduct whatever balance remains (should go to 0)
        profile = session.user.profile
        actual_deduction = min(energy_consumed, profile.balance_kwh)

        if actual_deduction > 0:
            profile.deduct_balance(actual_deduction)

            CreditTransaction.objects.create(
                user=session.user,
                amount_kwh=-actual_deduction,
                transaction_type=CreditTransaction.TransactionType.SESSION_DEBIT,
                session=session,
                description=f"Charging session at {session.station.name} (stopped - no credit)",
            )

        logger.warning(
            f"Session {session.id} stopped due to no credit. "
            f"Consumed: {energy_consumed} kWh, Charged: {actual_deduction} kWh"
        )

        return session

    @staticmethod
    def check_balance_and_stop(session: ChargingSession) -> bool:
        """
        Check if user has run out of balance and stop if needed.

        Args:
            session: The active session to check

        Returns:
            bool: True if session was stopped, False otherwise
        """
        if session.status != ChargingSession.SessionStatus.ACTIVE:
            return False

        profile = session.user.profile
        current_consumption = session.calculate_energy_consumed(session.station.current_energy)

        # If current consumption exceeds balance, stop the session
        if current_consumption >= profile.balance_kwh:
            ChargingService.stop_session_no_credit(session, session.station.current_energy)
            return True

        return False
