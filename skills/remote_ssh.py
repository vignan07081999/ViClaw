import paramiko
from skills.manager import BaseSkill

class RemoteSSHSkill(BaseSkill):
    name = "RemoteSSH"
    description = "Allows the agent to securely connect to remote servers via SSH and execute commands. Useful for managing IoT, Proxmox, TrueNAS, etc."

    def get_tools(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "execute_remote_ssh",
                    "description": "Executes a shell command on a remote machine using SSH.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "hostname": {"type": "string", "description": "The IP address or domain of the remote server."},
                            "username": {"type": "string", "description": "SSH username."},
                            "password": {"type": "string", "description": "SSH password (if key is not used)."},
                            "command": {"type": "string", "description": "The command to run on the server."}
                        },
                        "required": ["hostname", "username", "command"]
                    }
                }
            }
        ]

    def execute_remote_ssh(self, hostname, username, command, password=None):
        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Use paramiko to connect. It will try SSH Agent keys first, then fallback to password if provided
            connect_kwargs = {
                "hostname": hostname,
                "username": username,
                "timeout": 10
            }
            if password:
                connect_kwargs["password"] = password
                
            client.connect(**connect_kwargs)
            
            stdin, stdout, stderr = client.exec_command(command, timeout=30)
            
            exit_status = stdout.channel.recv_exit_status()
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            
            client.close()
            
            result = ""
            if out:
                result += f"STDOUT:\n{out}\n"
            if err:
                result += f"STDERR:\n{err}\n"
                
            return f"Command exited with status {exit_status}.\n{result}"
        except paramiko.AuthenticationException:
            return "Error: Authentication failed. Incorrect username/password, or SSH key missing."
        except Exception as e:
            return f"Remote SSH Error: {str(e)}"
