# What a process in the agent's container can reach. Same script run by the hook and by the agent.
w=$( (echo x > /etc/cs/hw-probe) 2>&1 && echo WROTE || echo DENIED )
echo "write /etc/cs: $w"
w2=$( (echo x > /usr/local/hw-probe) 2>&1 && echo WROTE || echo DENIED )
echo "write /usr/local: $w2"
if [ -e /etc/cs/mcp-config.json ]; then echo "read /etc/cs/mcp-config.json: EXISTS $(cat /etc/cs/mcp-config.json >/dev/null 2>&1 && echo READABLE || echo UNREADABLE)"; else echo "read /etc/cs/mcp-config.json: ABSENT"; fi
echo "list /etc/cs: $(ls /etc/cs 2>&1 | tr '\n' ' ' | cut -c1-120)"
echo "uid: $(id -u)"
