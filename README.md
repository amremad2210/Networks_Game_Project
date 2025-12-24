# Networks_Game_Project

### Instructions to Run locally
#### to try the game:
    1. make sure you have these packages installed: pip install pygame psutil
    2. in one terminal start the server: python3 ./server/server.py
    3. in another terminal start the client: python3 ./client/start_game/py
    4. the game window should appear, enter your username and enjoy!

### to run the baseline test:
    the baseline test script starts the server, and automates 2 clients, then prepares evalution metrics

    IMPORTANT: CHANGE THE PROJ_DIR VARIABLE IN THE basline.sh SCRIPT TO SUIT UR LOCAL MACHINE
    
    1. make sure you have these packages installed: pip install pygame psutil
    2. run the baseline test script: ./scripts/baseline.sh
    3. you get 6 files:
        a. client 1 log file (client id, reciever timestamps, displayed position, client bandwidth)
        b. client 2 log file (client id, reciever timestamps, displayed position, client bandwidth)
        c. server log file (snapshot id, seq_num, all player positions, cpu utilization)
        d. final metrics csv (has all fields required in the project document including percieved position  
           errors, latency, jitter, ...etc)
        e. metrics summary txt (has mean, median, percentiles for the calculated metrics)
        f. pcap_baseline.pcap (contains packets trace for reproducability)

### Demo video Link
https://drive.google.com/file/d/1wXnBoperX8RrRa1qzpkwAyy8vfxLC2qB/view?usp=sharing

