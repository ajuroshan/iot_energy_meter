import requests
from django.shortcuts import render, redirect
from django.http import JsonResponse

# ESP32 IP address (change according to your serial monitor output)
ESP32_IP = "http://192.168.137.194"  # Example

def pzem_data(request):
    try:
        response = requests.get(f"{ESP32_IP}/data", timeout=3)
        data = response.json()
    except Exception as e:
        data = {"error": str(e)}
    
    return render(request, "pzem_data.html", {"data": data})

def pzem_reset(request):
    try:
        requests.get(f"{ESP32_IP}/reset", timeout=3)
    except Exception as e:
        print(f"Error resetting: {e}")
    return redirect("pzem_data")
