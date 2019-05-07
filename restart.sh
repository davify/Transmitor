echo "Begin restart..."
echo "Killing... 1"
pkill Transmitor
pkill Transmitor
sleep 1
echo "Killing... 2"
pkill Transmitor
pkill Transmitor
sleep 1
echo "Killing... 3"
pkill Transmitor
pkill Transmitor
echo "Starting..."
nohup Transmitor > tmp 2>&1 &
tail -f tmp
