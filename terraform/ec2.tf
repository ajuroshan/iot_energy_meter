# EC2 Instance
resource "aws_instance" "app" {
  ami           = data.aws_ami.ubuntu.id
  instance_type = var.instance_type

  subnet_id                   = aws_subnet.public.id
  vpc_security_group_ids      = [aws_security_group.app.id]
  associate_public_ip_address = true
  key_name                    = var.key_pair_name

  user_data = templatefile("${path.module}/user_data.sh", {
    postgres_password = var.postgres_password
    django_secret_key = var.django_secret_key
    allowed_hosts     = var.domain_name != "" ? var.domain_name : "localhost"
    csrf_origins      = var.domain_name != "" ? "https://${var.domain_name}" : "http://localhost"
  })

  root_block_device {
    volume_size           = 30
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  tags = {
    Name = "${var.project_name}-server"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Elastic IP
resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}
