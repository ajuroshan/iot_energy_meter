output "instance_id" {
  description = "ID of the EC2 instance"
  value       = aws_instance.app.id
}

output "public_ip" {
  description = "Elastic IP address of the server"
  value       = aws_eip.app.public_ip
}

output "public_dns" {
  description = "Public DNS name of the server"
  value       = aws_eip.app.public_dns
}

output "ssh_command" {
  description = "SSH command to connect to the server"
  value       = "ssh -i ~/.ssh/${var.key_pair_name}.pem ubuntu@${aws_eip.app.public_ip}"
}

output "web_url" {
  description = "URL to access the web application"
  value       = var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_eip.app.public_ip}"
}

output "mqtt_endpoint" {
  description = "MQTT broker endpoint for ESP32 devices"
  value       = "${aws_eip.app.public_ip}:1883"
}

output "deployment_instructions" {
  description = "Instructions to complete deployment"
  value       = <<-EOT
    
    ============================================
    DEPLOYMENT INSTRUCTIONS
    ============================================
    
    1. SSH into the server:
       ${format("ssh -i ~/.ssh/%s.pem ubuntu@%s", var.key_pair_name, aws_eip.app.public_ip)}
    
    2. Clone your repository:
       cd /opt/energy-meter
       git clone <your-repo-url> app
    
    3. Start the application:
       docker compose up -d
    
    4. Create a superuser:
       docker compose exec web uv run python manage.py createsuperuser
    
    5. Access the application:
       Web: http://${aws_eip.app.public_ip}
       Admin: http://${aws_eip.app.public_ip}/admin
    
    6. Configure ESP32 devices with MQTT broker:
       Host: ${aws_eip.app.public_ip}
       Port: 1883
    
    ============================================
  EOT
}
