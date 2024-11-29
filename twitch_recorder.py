import subprocess
import time
import datetime
import os
import requests
from requests.exceptions import RequestException
from typing import Optional
import logging
from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('twitch_recorder.log'),
        logging.StreamHandler()
    ]
)

class TwitchRecorder:
    def __init__(self, channel: str, quality: str = '480p,360p,best'):
        self.channel = channel
        self.quality = quality
        self.output_dir = Path('recordings')
        self.output_dir.mkdir(exist_ok=True)
        
        # Twitch API credentials - replace with your own
        self.client_id = 'YOUR_CLIENT_ID'
        self.client_secret = 'YOUR_CLIENT_SECRET'
        self.twitch = None
        self.process: Optional[subprocess.Popen] = None
        
    async def initialize_twitch(self):
        """Initialize Twitch API client."""
        try:
            self.twitch = await Twitch(self.client_id, self.client_secret)
            logging.info("Successfully authenticated with Twitch API")
        except Exception as e:
            logging.error(f"Failed to initialize Twitch API: {e}")
            raise

    async def is_stream_live(self) -> bool:
        """Check if the channel is live using official Twitch API."""
        try:
            if not self.twitch:
                await self.initialize_twitch()
            
            stream = await first(self.twitch.get_streams(user_login=[self.channel]))
            return bool(stream)
        except Exception as e:
            logging.error(f"Error checking stream status: {e}")
            return False

    def is_internet_available(self) -> bool:
        """Check internet connectivity with multiple reliable endpoints."""
        endpoints = [
            'https://1.1.1.1',
            'https://8.8.8.8',
            'https://www.google.com'
        ]
        
        for endpoint in endpoints:
            try:
                requests.get(endpoint, timeout=5)
                return True
            except RequestException:
                continue
        return False

    def get_output_filename(self) -> Path:
        """Generate unique filename for the recording."""
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        return self.output_dir / f"{self.channel}_{timestamp}.mp4"

    def start_recording(self, filename: Path):
        """Start the recording process with streamlink."""
        command = [
            'streamlink',
            '--twitch-disable-hosting',
            '--twitch-disable-ads',
            '--retry-max', '5',
            '--retry-streams', '30',
            '--stream-timeout', '60',
            '--twitch-low-latency',
            f'twitch.tv/{self.channel}',
            self.quality,
            '-o', str(filename)
        ]
        
        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logging.info(f"Started recording to {filename}")

    def stop_recording(self):
        """Safely stop the recording process."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            logging.info("Recording stopped")

    async def record_stream(self):
        """Main recording loop with improved error handling."""
        while True:
            try:
                if not self.is_internet_available():
                    logging.warning("No internet connection")
                    time.sleep(30)
                    continue

                if not await self.is_stream_live():
                    logging.info(f"Channel {self.channel} is not live")
                    time.sleep(30)
                    continue

                filename = self.get_output_filename()
                self.start_recording(filename)

                while self.process and self.process.poll() is None:
                    if not await self.is_stream_live():
                        logging.info("Stream ended")
                        self.stop_recording()
                        break
                    time.sleep(30)

            except KeyboardInterrupt:
                logging.info("Recording interrupted by user")
                self.stop_recording()
                break
            except Exception as e:
                logging.error(f"Unexpected error: {e}")
                self.stop_recording()
                time.sleep(30)

if __name__ == "__main__":
    import asyncio
    
    # Configuration
    CHANNEL = 'SELECTED_CHANNEL'
    QUALITY = '480p,720p,720p60,360p,best'
    
    # Create and run recorder
    recorder = TwitchRecorder(CHANNEL, QUALITY)
    asyncio.run(recorder.record_stream())