# Command and Control (C2) Academic Simulation

> **WARNING:** This code is strictly for educational purposes in an isolated environment, such as a Host-Only VirtualBox or VMware network. It must not be used on real networks or without express authorization.
> 
> 

## Overview

This project simulates a basic malware beaconing and command execution cycle. The architecture utilizes HTTP requests to simulate how an implant communicates with an attacker-controlled server. To facilitate network traffic analysis with tools like Wireshark, the agent encodes command outputs using Base64 before transmission.

## Components

### 1. The Server (`servidor_c2.py`)

The server is an interactive Python Flask application that listens on port `8080` across all interfaces (`0.0.0.0`). The intended target environment IP for the server is `192.168.56.100`.

* **Interactive Console:** Runs in a separate daemon thread, allowing the operator to queue commands for specific agents without blocking the Flask web server.


* **Thread-Safety:** Utilizes a threading lock to ensure safe interactions between the Flask routes and the console.


* **Logging:** Maintains a history of received beacons and exfiltrated results in memory, which are printed to the console.



### 2. The Agent (`agent.c`)

The agent is a C program that utilizes `libcurl` to communicate with the C2 server.

* **Beaconing:** Polling occurs on an exact 10-second interval where the agent requests its next instruction.


* **Configuration:** By default, the agent is configured with the ID `maquina01` and connects to the server at `[http://127.0.0.1:8080](http://127.0.0.1:8080)`.


* **Execution:** Commands are executed using `popen`, allowing the agent to read the terminal output.


* **Exfiltration:** The terminal output is encoded into Base64, URL-escaped, and sent back to the server via an HTTP POST request.



## API Routes

The Flask server implements the following endpoints to handle agent communication and monitoring:

* **`GET /check`**: The route agents call to fetch their next command. It expects an `id` parameter (e.g., `?id=maquina01`) and returns plain text. If the queue is empty, it returns `NONE`.


* **`POST /result`**: The route used for data exfiltration. It accepts `application/x-www-form-urlencoded` payloads containing the agent `id` and the Base64-encoded `output`. The server decodes this data and displays it on the operator's terminal.


* **`GET /status`**: A bonus dashboard endpoint that returns a JSON response containing connected agents, pending command queues, total beacons, total results, and the most recent result.



## Whitelisted Commands

To maintain a streamlined scope and prevent arbitrary code execution, both the server and the agent enforce a strict whitelist of permitted commands.

* `whoami`

* `ipconfig`

* `dir`

* `ls`

* `SHUTDOWN_AGENT`: Acts as a kill switch that forces the agent to terminate its own process cleanly.



## Getting Started

### Running the Server

1. Install the required dependencies: `pip install flask`.


2. Execute the Python script: `python servidor_c2.py`.


3. Use the interactive console to input the target agent ID (e.g., `maquina01`) and select a command from the whitelist.



### Running the Agent

1. Ensure the `libcurl` development libraries are installed on your system.
2. Compile the `agent.c` file.
3. Run the compiled executable to initiate the 10-second beaconing loop.
