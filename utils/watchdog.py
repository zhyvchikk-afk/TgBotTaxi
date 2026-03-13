import subprocess
import time

def run_bot():
    while True:
        process = subprocess.Popen(["python", "main.py"])
        process.wait()
        print("Bot stopped. Restarting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    run_bot()
