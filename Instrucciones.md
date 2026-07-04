# Instrucciones de XLuckyMiner

Guía paso a paso para configurar, instalar y ejecutar tu minero de Bitcoin en solitario (Solo Mining).

---

## 1. Requisitos Generales (Ambos Sistemas)

*   **Nodo de Bitcoin (Bitcoin Core)**:
    *   Debes tener instalado y sincronizado **Bitcoin Core**.
    *   Debes habilitar el servidor RPC en el archivo de configuración `bitcoin.conf`.
    *   Añade o modifica estas líneas:
        ```ini
        server=1
        rpcuser=tu_usuario
        rpcpassword=tu_contraseña
        rpcallowip=127.0.0.1
        ```
    *   Reinicia Bitcoin Core para aplicar los cambios.

---

## 2. Guía para Windows

### Requisitos Windows
*   **Python**: Instala Python 3.8+ desde [python.org](https://www.python.org/downloads/windows/). Asegúrate de marcar "Add Python to PATH" durante la instalación.
*   **Drivers GPU**: Instala los últimos drivers de NVIDIA o AMD.

### Instalación en Windows
1.  Abre el **Símbolo del sistema (CMD)** o **PowerShell**.
2.  Navega a la carpeta del proyecto:
    ```cmd
    cd ruta\a\XLuckyMiner
    ```
3.  Instala las dependencias:
    ```cmd
    pip install -r requirements.txt
    ```

### Ejecución en Windows
```cmd
python main.py
```

---

## 3. Guía para Linux (Ubuntu)

### Requisitos Ubuntu
*   **Python**: Normalmente ya viene instalado. Instala `pip` y `venv` si no los tienes:
    ```bash
    sudo apt update
    sudo apt install python3-pip python3-venv
    ```
*   **Drivers GPU (OpenCL)**:
    *   **NVIDIA**: Instala el toolkit de CUDA (incluye OpenCL).
        ```bash
        sudo apt install nvidia-cuda-toolkit      # Debian/Ubuntu
        ```
    *   **AMD (ROCm)**: Necesitás el ICD de OpenCL de ROCm y, para el watchdog, `amdsmi`.
        ```bash
        # Debian/Ubuntu:
        sudo apt install rocm-opencl-runtime amd-smi-lib
        # Fedora:
        sudo dnf install rocm-opencl amdsmi opencl-headers
        ```
    *   Verificá que la GPU aparezca: `python3 -c "import pyopencl as cl; print(cl.get_platforms())"`.

### Instalación en Ubuntu
1.  Abre una terminal.
2.  Navega a la carpeta del proyecto:
    ```bash
    cd /ruta/a/XLuckyMiner
    ```
3.  (Opcional pero recomendado) Crea un entorno virtual:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
4.  Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```

### Ejecución en Ubuntu
```bash
python3 main.py
```

---

## 4. Configuración (Común)

Abre el archivo `config.py` con cualquier editor de texto y configura:

1.  **Credenciales RPC**:
    *   `RPC_URL`: `http://127.0.0.1:8332`
    *   `RPC_USER` y `RPC_PASSWORD`: Los mismos de tu `bitcoin.conf`.

2.  **Tu Billetera (Wallet)**:
    *   `WALLET_ADDRESS`: Pega tu dirección de Bitcoin aquí.

3.  **Límite de Carga**:
    *   `GPU_LOAD_LIMIT_PERCENT`: Porcentaje de uso de GPU (ej. `30`).

4.  **Watchdog (opcional)**: control automático de arranque/pausa según el uso de GPU.
    *   `PAUSE_THRESHOLD_PERCENT`: pausa el minero si el uso TOTAL de la GPU supera esto. Dejalo bastante por encima de `GPU_LOAD_LIMIT_PERCENT` o el minero se pausaría a sí mismo.
    *   `IDLE_THRESHOLD_PERCENT` + `IDLE_WAIT_MINUTES`: arranca el minero tras ese tiempo de GPU inactiva (por defecto 10 min).

## 5. Ejecución con Watchdog (recomendado)

En vez de correr `main.py` directo, podés dejar que el watchdog lo administre: arranca cuando la GPU está libre y lo pausa cuando otra app la necesita.

```bash
python3 watchdog.py         # espera a que la GPU esté inactiva
python3 watchdog.py --now    # arranca ya, sin esperar
```

## 6. ¿Cómo recibo mis fondos?

*   **Solo Mining**: Es tu PC contra la red.
*   **El Pago**: Si encuentras un bloque, la red genera una **Coinbase Transaction** de **3.125 BTC** (+ comisiones) directamente a tu `WALLET_ADDRESS`.
