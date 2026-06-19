provider "aws" {
  region = "us-east-1"
}

# ──────────────── Security Group ────────────────
data "aws_security_group" "launch_wizard" {
  filter {
    name   = "group-name"
    values = ["launch-wizard-2"]
  }
}

# ──────────────── EC2 Instance ────────────────
resource "aws_instance" "media_intel" {
  ami                    = "ami-0fc5d935ebf8bc3bc" # Ubuntu 22.04 LTS us-east-1
  instance_type          = "t3.xlarge"
  key_name               = "wldsh-dev"
  vpc_security_group_ids = [data.aws_security_group.launch_wizard.id]

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
  }

  tags = {
    Name        = "MediaIntelligenceAPI"
    Environment = "production"
    Project     = "aisec-digital-risk"
  }
}

# ──────────────── Outputs ────────────────
output "instance_public_ip" {
  value = aws_instance.media_intel.public_ip
}

output "instance_id" {
  value = aws_instance.media_intel.id
}

# ──────────────── Generate Ansible Inventory ────────────────
resource "local_file" "ansible_inventory" {
  content = <<-EOF
    [media_intel]
    ${aws_instance.media_intel.public_ip} ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/wldsh-dev.pem

    [media_intel:vars]
    ansible_python_interpreter=/usr/bin/python3
  EOF

  filename = "${path.module}/../ansible/inventory"
}
