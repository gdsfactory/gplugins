import base64
import os

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


def load_schemedit_wasm_b64():
    schemedit_wasm = open(os.path.join(STATIC_DIR, "schemedit.wasm"), "rb").read()
    schemedit_wasm_b64 = base64.b64encode(schemedit_wasm)
    return schemedit_wasm_b64.decode()


if __name__ == "__main__":
    print(load_schemedit_wasm_b64()[:10])
