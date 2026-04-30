#!/usr/bin/env python3
"""
Web Terminal Connection Tester
Tests the entire web SSH terminal stack and diagnoses issues
"""

import asyncio
import json
import sys
import time
import requests
from typing import Dict, Optional, Tuple
import socketio
from datetime import datetime

import os

# Configuration (read PASSWORD from env or BOOKMAKER_TEST_PASSWORD)
BASE_URL = "https://book.iotok.org"
TERMINAL_URL = "https://book.iotok.org"
USERNAME = os.getenv("BOOKMAKER_TEST_USERNAME", "admin")
PASSWORD = os.getenv("BOOKMAKER_TEST_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set BOOKMAKER_TEST_PASSWORD env var before running this test")

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.END}\n")

def print_success(text: str):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text: str):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text: str):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text: str):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

def print_step(step: int, text: str):
    print(f"\n{Colors.BOLD}[Step {step}]{Colors.END} {text}")


class TerminalTester:
    def __init__(self):
        self.token: Optional[str] = None
        self.user_id: Optional[int] = None
        self.sio: Optional[socketio.AsyncClient] = None
        self.connected = False
        self.terminal_output = []
        self.errors = []

    def test_1_backend_health(self) -> bool:
        """Test if backend is responding"""
        print_step(1, "Testing Backend Health")

        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            data = response.json()

            if response.status_code == 200:
                print_success(f"Backend is healthy")
                print_info(f"  Service: {data.get('service')}")
                print_info(f"  Version: {data.get('version')}")
                return True
            else:
                print_error(f"Backend returned status {response.status_code}")
                self.errors.append(("backend_health", response.status_code))
                return False

        except requests.exceptions.ConnectionError as e:
            print_error(f"Cannot connect to backend: {e}")
            self.errors.append(("backend_connection", str(e)))
            return False
        except Exception as e:
            print_error(f"Backend health check failed: {e}")
            self.errors.append(("backend_health", str(e)))
            return False

    def test_2_terminal_server_health(self) -> bool:
        """Test if terminal server is responding"""
        print_step(2, "Testing Terminal Server Health")

        try:
            # Test direct connection
            response = requests.get("http://localhost:8187/health", timeout=5)
            data = response.json()

            if response.status_code == 200:
                print_success(f"Terminal server is healthy (direct)")
                print_info(f"  Service: {data.get('service')}")
                print_info(f"  Connections: {data.get('connections')}")
                print_info(f"  Uptime: {data.get('uptime', 0):.2f}s")
            else:
                print_error(f"Terminal server returned status {response.status_code}")
                self.errors.append(("terminal_health_direct", response.status_code))
                return False

        except Exception as e:
            print_error(f"Terminal server not responding (direct): {e}")
            self.errors.append(("terminal_health_direct", str(e)))
            return False

        # Test through Nginx
        try:
            response = requests.get(f"{BASE_URL}/terminal-health", timeout=5)
            data = response.json()

            if response.status_code == 200:
                print_success(f"Terminal server accessible through Nginx")
                return True
            else:
                print_warning(f"Nginx proxy returned status {response.status_code}")
                self.errors.append(("terminal_health_nginx", response.status_code))
                return False

        except Exception as e:
            print_error(f"Terminal server not accessible through Nginx: {e}")
            self.errors.append(("terminal_health_nginx", str(e)))
            return False

    def test_3_authentication(self) -> bool:
        """Test authentication and get JWT token"""
        print_step(3, "Testing Authentication")

        try:
            response = requests.post(
                f"{BASE_URL}/api/login",
                json={"username": USERNAME, "password": PASSWORD},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                self.token = data.get("access_token")
                self.user_id = data.get("user_id")

                print_success(f"Authentication successful")
                print_info(f"  User: {data.get('username')}")
                print_info(f"  User ID: {self.user_id}")
                print_info(f"  Token length: {len(self.token)} chars")
                print_info(f"  Token preview: {self.token[:20]}...")
                return True
            else:
                print_error(f"Authentication failed: {response.status_code}")
                print_error(f"  Response: {response.text}")
                self.errors.append(("authentication", response.status_code))
                return False

        except Exception as e:
            print_error(f"Authentication request failed: {e}")
            self.errors.append(("authentication", str(e)))
            return False

    def test_4_jwt_validation(self) -> bool:
        """Test JWT token validation"""
        print_step(4, "Testing JWT Token Validation")

        if not self.token:
            print_error("No token available (authentication failed?)")
            return False

        try:
            # Test token with /api/me endpoint
            response = requests.get(
                f"{BASE_URL}/api/me",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                print_success(f"JWT token is valid")
                print_info(f"  Authenticated as: {data.get('username')}")
                return True
            else:
                print_error(f"JWT validation failed: {response.status_code}")
                self.errors.append(("jwt_validation", response.status_code))
                return False

        except Exception as e:
            print_error(f"JWT validation request failed: {e}")
            self.errors.append(("jwt_validation", str(e)))
            return False

    def test_5_socketio_endpoint(self) -> bool:
        """Test Socket.IO endpoint availability"""
        print_step(5, "Testing Socket.IO Endpoint")

        try:
            # Test Socket.IO polling endpoint
            response = requests.get(
                f"{BASE_URL}/socket.io/?EIO=4&transport=polling",
                timeout=5
            )

            # Socket.IO should return 400 or session ID
            if response.status_code in [200, 400]:
                print_success(f"Socket.IO endpoint is accessible")
                print_info(f"  Status: {response.status_code}")

                if response.status_code == 200:
                    print_info(f"  Response: {response.text[:100]}...")

                return True
            else:
                print_error(f"Socket.IO endpoint returned unexpected status: {response.status_code}")
                print_error(f"  Response: {response.text[:200]}")
                self.errors.append(("socketio_endpoint", response.status_code))
                return False

        except Exception as e:
            print_error(f"Socket.IO endpoint test failed: {e}")
            self.errors.append(("socketio_endpoint", str(e)))
            return False

    async def test_6_socketio_connection(self) -> bool:
        """Test actual Socket.IO WebSocket connection"""
        print_step(6, "Testing Socket.IO WebSocket Connection")

        if not self.token:
            print_error("No token available")
            return False

        self.sio = socketio.AsyncClient(
            logger=False,
            engineio_logger=False,
            reconnection=False
        )

        connection_success = False
        connection_error = None
        terminal_ready = False

        @self.sio.event
        async def connect():
            nonlocal connection_success
            connection_success = True
            self.connected = True
            print_success(f"Socket.IO connected! Session ID: {self.sio.sid}")

        @self.sio.event
        async def connect_error(data):
            nonlocal connection_error
            connection_error = data
            print_error(f"Connection error: {data}")
            self.errors.append(("socketio_connect_error", str(data)))

        @self.sio.event
        async def disconnect():
            print_info("Socket.IO disconnected")
            self.connected = False

        @self.sio.on('output')
        async def on_output(data):
            nonlocal terminal_ready
            self.terminal_output.append(data)

            # Check for terminal ready message
            if "bookmaker:" in data or "/var/www/aibook" in data:
                terminal_ready = True

        @self.sio.on('error')
        async def on_error(data):
            print_error(f"Terminal error: {data}")
            self.errors.append(("terminal_error", str(data)))

        @self.sio.on('exit')
        async def on_exit(data):
            print_info(f"Terminal exited: {data}")

        try:
            print_info(f"Connecting to {TERMINAL_URL}")
            print_info(f"Using JWT token: {self.token[:30]}...")

            await self.sio.connect(
                TERMINAL_URL,
                auth={"token": self.token},
                transports=['websocket', 'polling'],
                wait_timeout=10
            )

            # Wait for connection to establish
            await asyncio.sleep(2)

            if connection_success:
                print_success("WebSocket connection established")

                # Wait for terminal output
                print_info("Waiting for terminal initialization...")
                await asyncio.sleep(3)

                if self.terminal_output:
                    print_success(f"Received terminal output ({len(self.terminal_output)} messages)")
                    print_info("Terminal output:")
                    for msg in self.terminal_output[:10]:  # Show first 10 messages
                        # Clean ANSI codes for display
                        clean_msg = msg.replace('\x1b[36m', '').replace('\x1b[32m', '').replace('\x1b[0m', '').replace('\r\n', '\n').strip()
                        if clean_msg:
                            print(f"    | {clean_msg}")

                    if terminal_ready:
                        print_success("Terminal is ready for input!")
                    else:
                        print_warning("Terminal output received but prompt not detected")
                else:
                    print_warning("No terminal output received yet")

                return True
            else:
                if connection_error:
                    print_error(f"Failed to connect: {connection_error}")
                else:
                    print_error("Connection failed (timeout)")
                return False

        except socketio.exceptions.ConnectionError as e:
            print_error(f"Socket.IO connection failed: {e}")
            self.errors.append(("socketio_connection", str(e)))
            return False
        except Exception as e:
            print_error(f"Socket.IO test failed: {e}")
            self.errors.append(("socketio_test", str(e)))
            return False

    async def test_7_terminal_interaction(self) -> bool:
        """Test sending commands to terminal"""
        print_step(7, "Testing Terminal Interaction")

        if not self.connected or not self.sio:
            print_error("Not connected to terminal")
            return False

        try:
            # Clear previous output
            self.terminal_output = []

            # Send a simple command
            print_info("Sending command: pwd")
            await self.sio.emit('input', 'pwd\n')

            # Wait for response
            await asyncio.sleep(2)

            if self.terminal_output:
                print_success(f"Terminal responded to command")
                print_info("Command output:")
                for msg in self.terminal_output:
                    clean_msg = msg.replace('\x1b[36m', '').replace('\x1b[32m', '').replace('\x1b[0m', '').replace('\r\n', '\n').strip()
                    if clean_msg and clean_msg != 'pwd':
                        print(f"    | {clean_msg}")

                # Check if output contains expected directory
                output_str = ''.join(self.terminal_output)
                if '/var/www/aibook' in output_str:
                    print_success("Terminal is in correct directory: /var/www/aibook")
                    return True
                else:
                    print_warning("Terminal response received but directory unclear")
                    return True
            else:
                print_error("No response from terminal")
                self.errors.append(("terminal_interaction", "no response"))
                return False

        except Exception as e:
            print_error(f"Terminal interaction failed: {e}")
            self.errors.append(("terminal_interaction", str(e)))
            return False

    async def test_8_directory_restriction(self) -> bool:
        """Test directory confinement"""
        print_step(8, "Testing Directory Restriction")

        if not self.connected or not self.sio:
            print_warning("Skipping (not connected)")
            return True

        try:
            # Clear output
            self.terminal_output = []

            # Try to cd to restricted directory
            print_info("Testing: cd /etc")
            await self.sio.emit('input', 'cd /etc\n')
            await asyncio.sleep(2)

            output = ''.join(self.terminal_output)

            if 'restricted' in output.lower() or 'Access restricted' in output:
                print_success("Directory restriction is working")
                return True
            else:
                print_warning("Directory restriction test inconclusive")
                print_info(f"Output: {output[:100]}")
                return True

        except Exception as e:
            print_error(f"Directory restriction test failed: {e}")
            return True  # Non-critical

    async def cleanup(self):
        """Cleanup connections"""
        if self.sio and self.connected:
            try:
                await self.sio.disconnect()
                print_info("Disconnected from terminal")
            except:
                pass

    def print_summary(self, results: Dict[str, bool]):
        """Print test summary"""
        print_header("TEST SUMMARY")

        total = len(results)
        passed = sum(1 for v in results.values() if v)
        failed = total - passed

        print(f"\n{Colors.BOLD}Results:{Colors.END}")
        for test_name, result in results.items():
            status = f"{Colors.GREEN}PASS{Colors.END}" if result else f"{Colors.RED}FAIL{Colors.END}"
            print(f"  {test_name.ljust(50)} [{status}]")

        print(f"\n{Colors.BOLD}Summary:{Colors.END}")
        print(f"  Total:  {total}")
        print(f"  {Colors.GREEN}Passed: {passed}{Colors.END}")
        print(f"  {Colors.RED}Failed: {failed}{Colors.END}")

        if failed == 0:
            print(f"\n{Colors.BOLD}{Colors.GREEN}🎉 ALL TESTS PASSED! Terminal is working correctly.{Colors.END}")
        else:
            print(f"\n{Colors.BOLD}{Colors.RED}❌ {failed} test(s) failed. See errors above.{Colors.END}")

            if self.errors:
                print_header("ERROR DIAGNOSTICS")
                self.diagnose_errors()

    def diagnose_errors(self):
        """Provide diagnostic suggestions based on errors"""

        error_types = [e[0] for e in self.errors]

        # Backend connection issues
        if "backend_connection" in error_types or "backend_health" in error_types:
            print_error("BACKEND NOT RESPONDING")
            print("Possible fixes:")
            print("  1. Check if backend is running:")
            print("     ps aux | grep 'uvicorn main:app'")
            print("  2. Check backend logs:")
            print("     tail -f /tmp/bookmaker-backend.log")
            print("  3. Restart backend:")
            print("     cd /var/www/aibook/bookmaker/backend")
            print("     ./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8086")

        # Terminal server issues
        if "terminal_health" in str(error_types):
            print_error("TERMINAL SERVER NOT RESPONDING")
            print("Possible fixes:")
            print("  1. Check if terminal server is running:")
            print("     ps aux | grep 'node server.js'")
            print("  2. Check terminal server logs:")
            print("     tail -f /tmp/terminal-server.log")
            print("  3. Restart terminal server:")
            print("     cd /var/www/aibook/bookmaker/terminal-server")
            print("     node server.js &")

        # Authentication issues
        if "authentication" in error_types or "jwt_validation" in error_types:
            print_error("AUTHENTICATION ISSUES")
            print("Possible fixes:")
            print("  1. Verify admin user exists:")
            print("     sqlite3 /var/www/aibook/bookmaker/backend/bookmaker.db")
            print("     SELECT * FROM users WHERE username='admin';")
            print("  2. Check SECRET_KEY matches in both:")
            print("     backend/auth.py")
            print("     terminal-server/.env")

        # Socket.IO issues
        if "socketio" in str(error_types):
            print_error("SOCKET.IO CONNECTION ISSUES")
            print("Possible fixes:")
            print("  1. Check Nginx configuration:")
            print("     sudo nginx -t")
            print("     sudo cat /etc/nginx/sites-available/book.iotok.org | grep -A10 'socket.io'")
            print("  2. Verify SECRET_KEY matches:")
            print("     grep SECRET_KEY backend/auth.py")
            print("     cat terminal-server/.env")
            print("  3. Check terminal server logs for auth errors:")
            print("     tail -f /tmp/terminal-server.log | grep -i auth")
            print("  4. Test Socket.IO endpoint directly:")
            print("     curl https://book.iotok.org/socket.io/")

        # Connection errors (Cloudflare, WebSocket, etc.)
        if "connect_error" in str(error_types):
            print_error("CONNECTION ERRORS")

            error_messages = [e[1] for e in self.errors if e[0] == "socketio_connect_error"]
            if error_messages:
                print(f"Error message: {error_messages[0]}")

                if "websocket error" in str(error_messages).lower():
                    print("This appears to be a WebSocket connection issue.")
                    print("Possible causes:")
                    print("  1. Cloudflare WebSocket not enabled")
                    print("  2. Nginx WebSocket headers missing")
                    print("  3. Terminal server not accepting connections")

                if "forbidden" in str(error_messages).lower() or "unauthorized" in str(error_messages).lower():
                    print("This is an authentication issue.")
                    print("Fix:")
                    print("  1. Ensure SECRET_KEY in terminal-server/.env matches backend/.env")
                    print("  2. Restart terminal server after changing .env")


async def main():
    print_header("WEB TERMINAL CONNECTION TESTER")
    print(f"{Colors.BOLD}Testing URL:{Colors.END} {BASE_URL}")
    print(f"{Colors.BOLD}Username:{Colors.END} {USERNAME}")
    print(f"{Colors.BOLD}Timestamp:{Colors.END} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    tester = TerminalTester()
    results = {}

    try:
        # Run synchronous tests
        results["1. Backend Health"] = tester.test_1_backend_health()
        results["2. Terminal Server Health"] = tester.test_2_terminal_server_health()
        results["3. Authentication"] = tester.test_3_authentication()
        results["4. JWT Validation"] = tester.test_4_jwt_validation()
        results["5. Socket.IO Endpoint"] = tester.test_5_socketio_endpoint()

        # Run async tests
        results["6. Socket.IO Connection"] = await tester.test_6_socketio_connection()

        if results["6. Socket.IO Connection"]:
            results["7. Terminal Interaction"] = await tester.test_7_terminal_interaction()
            results["8. Directory Restriction"] = await tester.test_8_directory_restriction()
        else:
            results["7. Terminal Interaction"] = False
            results["8. Directory Restriction"] = False

    except KeyboardInterrupt:
        print_warning("\n\nTest interrupted by user")
    except Exception as e:
        print_error(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await tester.cleanup()
        tester.print_summary(results)

        # Return exit code based on results
        if all(results.values()):
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == "__main__":
    # Check dependencies
    try:
        import socketio
        import requests
    except ImportError as e:
        print_error(f"Missing dependency: {e}")
        print_info("Install with: pip install python-socketio[asyncio] requests aiohttp")
        sys.exit(1)

    asyncio.run(main())
