#!/usr/bin/env python3
"""
Django Slack Bot - ngrok Helper
===============================

This script provides utilities for running ngrok alongside Django.
It can automatically start ngrok, retrieve the public URL, and open
the ngrok web interface in your browser.

Usage:
    python scripts/ngrok_helper.py [options]
    
Options:
    --start         Start ngrok tunnel
    --url           Get the current ngrok public URL
    --open          Open ngrok web interface in browser
    --status        Check ngrok status
    --help          Show this help message
"""

import json
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
import requests
import argparse
import os
import signal


class NgrokHelper:
    def __init__(self):
        self.ngrok_api_url = "http://localhost:4040/api/tunnels"
        self.ngrok_web_url = "http://localhost:4040"
        self.django_port = 8000
        self.ngrok_process = None
        
    def find_ngrok_executable(self):
        """Find ngrok executable path"""
        # Check if ngrok is in current directory
        local_ngrok = Path("./ngrok")
        if local_ngrok.exists():
            return str(local_ngrok.absolute())
        
        # Check if ngrok is in PATH
        try:
            result = subprocess.run(["which", "ngrok"], 
                                  capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
        
        # Check common installation paths
        common_paths = [
            "/usr/local/bin/ngrok",
            "/opt/homebrew/bin/ngrok",
            "~/ngrok",
            "./ngrok"
        ]
        
        for path in common_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                return str(expanded_path.absolute())
        
        return None
    
    def is_ngrok_running(self):
        """Check if ngrok is currently running"""
        try:
            response = requests.get(self.ngrok_api_url, timeout=5)
            return response.status_code == 200
        except requests.RequestException:
            return False
    
    def is_django_running(self):
        """Check if Django is running on the expected port"""
        try:
            response = requests.get(f"http://localhost:{self.django_port}", timeout=5)
            return True
        except requests.RequestException:
            return False
    
    def get_public_url(self):
        """Get the current ngrok public URL"""
        if not self.is_ngrok_running():
            return None
        
        try:
            response = requests.get(self.ngrok_api_url, timeout=10)
            data = response.json()
            
            tunnels = data.get("tunnels", [])
            for tunnel in tunnels:
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
            
            # Fallback to http if https not found
            for tunnel in tunnels:
                if tunnel.get("proto") == "http":
                    url = tunnel.get("public_url")
                    # Convert to https if possible
                    if url and url.startswith("http://"):
                        return url.replace("http://", "https://", 1)
                    return url
                    
        except requests.RequestException as e:
            print(f"❌ Error getting ngrok URL: {e}")
            
        return None
    
    def start_ngrok(self, wait_for_django=True):
        """Start ngrok tunnel"""
        ngrok_path = self.find_ngrok_executable()
        if not ngrok_path:
            print("❌ ngrok not found. Please run ./setup_ngrok.sh first")
            return False
        
        if self.is_ngrok_running():
            print("⚠️  ngrok is already running")
            return True
        
        if wait_for_django and not self.is_django_running():
            print("⚠️  Django server not detected on port 8000")
            print("💡 Make sure Django is running first: ./run.sh")
            return False
        
        print("🚀 Starting ngrok tunnel...")
        
        try:
            # Start ngrok in background
            self.ngrok_process = subprocess.Popen([
                ngrok_path, "http", str(self.django_port),
                "--log", "stdout"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Wait for ngrok to start
            for i in range(10):
                time.sleep(1)
                if self.is_ngrok_running():
                    break
                if self.ngrok_process.poll() is not None:
                    # Process has terminated
                    stdout, stderr = self.ngrok_process.communicate()
                    print(f"❌ ngrok failed to start:")
                    print(stderr.decode())
                    return False
            else:
                print("❌ ngrok took too long to start")
                self.stop_ngrok()
                return False
            
            # Get and display the public URL
            url = self.get_public_url()
            if url:
                print(f"✅ ngrok tunnel started successfully!")
                print(f"🔗 Public URL: {url}")
                print(f"🔗 Slack Events: {url}/slack/events/")
                print(f"🔗 Slack Commands: {url}/slack/commands/")
                print(f"🌐 ngrok Web Interface: {self.ngrok_web_url}")
                return True
            else:
                print("⚠️  ngrok started but couldn't retrieve public URL")
                return True
                
        except Exception as e:
            print(f"❌ Error starting ngrok: {e}")
            return False
    
    def stop_ngrok(self):
        """Stop ngrok tunnel"""
        if self.ngrok_process:
            self.ngrok_process.terminate()
            self.ngrok_process.wait()
            print("🛑 ngrok stopped")
    
    def open_web_interface(self):
        """Open ngrok web interface in browser"""
        if not self.is_ngrok_running():
            print("❌ ngrok is not running")
            return False
        
        try:
            webbrowser.open(self.ngrok_web_url)
            print(f"🌐 Opening ngrok web interface: {self.ngrok_web_url}")
            return True
        except Exception as e:
            print(f"❌ Error opening web interface: {e}")
            return False
    
    def show_status(self):
        """Show current status of ngrok and Django"""
        print("📊 Service Status:")
        print("=" * 20)
        
        django_status = "✅ Running" if self.is_django_running() else "❌ Not running"
        print(f"Django (port {self.django_port}): {django_status}")
        
        ngrok_status = "✅ Running" if self.is_ngrok_running() else "❌ Not running"
        print(f"ngrok: {ngrok_status}")
        
        if self.is_ngrok_running():
            url = self.get_public_url()
            if url:
                print(f"Public URL: {url}")
                print(f"Events URL: {url}/slack/events/")
                print(f"Commands URL: {url}/slack/commands/")
            print(f"Web Interface: {self.ngrok_web_url}")
    
    def run_with_django(self):
        """Run ngrok alongside Django (integrated mode)"""
        print("🚀 Starting Django + ngrok Development Environment")
        print("=" * 55)
        
        # Start Django in background
        print("📦 Starting Django server...")
        django_process = subprocess.Popen([
            "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
            "manage.py", "runserver", f"127.0.0.1:{self.django_port}"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait for Django to start
        time.sleep(3)
        
        if not self.is_django_running():
            print("❌ Failed to start Django server")
            django_process.terminate()
            return False
        
        print("✅ Django server started")
        
        # Start ngrok
        if not self.start_ngrok(wait_for_django=False):
            print("❌ Failed to start ngrok")
            django_process.terminate()
            return False
        
        # Set up signal handlers for cleanup
        def cleanup(signum, frame):
            print("\n🛑 Shutting down servers...")
            self.stop_ngrok()
            django_process.terminate()
            django_process.wait()
            print("✅ Cleanup completed")
            sys.exit(0)
        
        signal.signal(signal.SIGINT, cleanup)
        signal.signal(signal.SIGTERM, cleanup)
        
        print("\n🎉 Development environment ready!")
        print("Press Ctrl+C to stop both servers")
        print("\n📋 Quick Actions:")
        print("  • Open web interface: python scripts/ngrok_helper.py --open")
        print("  • Check status: python scripts/ngrok_helper.py --status")
        print("")
        
        # Keep running until interrupted
        try:
            django_process.wait()
        except KeyboardInterrupt:
            cleanup(None, None)


def main():
    parser = argparse.ArgumentParser(
        description="Django Slack Bot - ngrok Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("--start", action="store_true",
                       help="Start ngrok tunnel")
    parser.add_argument("--url", action="store_true",
                       help="Get current ngrok public URL")
    parser.add_argument("--open", action="store_true",
                       help="Open ngrok web interface in browser")
    parser.add_argument("--status", action="store_true",
                       help="Show ngrok and Django status")
    parser.add_argument("--integrated", action="store_true",
                       help="Run Django and ngrok together")
    
    args = parser.parse_args()
    
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    helper = NgrokHelper()
    
    if args.status:
        helper.show_status()
    elif args.url:
        url = helper.get_public_url()
        if url:
            print(url)
        else:
            print("❌ No ngrok URL available")
            sys.exit(1)
    elif args.open:
        helper.open_web_interface()
    elif args.start:
        helper.start_ngrok()
    elif args.integrated:
        helper.run_with_django()
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 