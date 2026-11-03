# Instalación OCR DEV

No había `tesseract` ni traineddata hebreo. `sudo -n true` devolvió 1; no se pidió password ni se instaló a nivel sistema. Se usó instalación extraída en espacio de usuario, sin sustituir motor.

Origen: repositorio apt configurado Ubuntu noble/universe, `http://archive.ubuntu.com/ubuntu`. Paquetes y SHA-256 exactos en `ocr-environment.json`:

| Package | Version | Motivo |
|---|---|---|
| tesseract-ocr | 5.3.4-1build5 | ejecutable Tesseract 5 |
| libtesseract5 | 5.3.4-1build5 | dependencia mínima |
| liblept5 | 1.82.0-3build4 | dependencia mínima de imágenes |
| tesseract-ocr-heb | 1:4.1.0-2 | modelo hebreo packaged tessdata |
| tesseract-ocr-spa | 1:4.1.0-2 | únicamente controles español/columnas |

Comandos ejecutados:

```bash
mkdir -p /tmp/tebaai-ocr-install
cd /tmp/tebaai-ocr-install
apt-get download tesseract-ocr tesseract-ocr-heb tesseract-ocr-spa libtesseract5
apt-get download liblept5
mkdir -p /home/issajar/.local/opt/tebaai-ocr-v1
for p in *.deb; do dpkg-deb -x "$p" /home/issajar/.local/opt/tebaai-ocr-v1; done
LD_LIBRARY_PATH=/home/issajar/.local/opt/tebaai-ocr-v1/usr/lib/x86_64-linux-gnu \
 /home/issajar/.local/opt/tebaai-ocr-v1/usr/bin/tesseract --version
LD_LIBRARY_PATH=/home/issajar/.local/opt/tebaai-ocr-v1/usr/lib/x86_64-linux-gnu \
 /home/issajar/.local/opt/tebaai-ocr-v1/usr/bin/tesseract \
 --tessdata-dir /home/issajar/.local/opt/tebaai-ocr-v1/usr/share/tesseract-ocr/5/tessdata --list-langs
```

Intento inicial: faltaba `liblept.so.5`. La consulta errónea `apt-get download libleptonica6` falló (nombre inexistente); `apt-cache depends libtesseract5` identificó `liblept5`, descargado y extraído. No fallback de motor.

Verificados: Tesseract 5.3.4, Leptonica 1.82.0, heb/spa disponibles; reconocimiento real del render original. Traineddata en `~/.local/opt/tebaai-ocr-v1/usr/share/tesseract-ocr/5/tessdata/{heb,spa}.traineddata`. La versión 4.1.0 es la del paquete/modelo, no la del engine. Sin PATH global, shell rc, imágenes base, suites OCR adicionales ni servicio persistente. Motor ejecutado offline; sólo descarga de paquetes utilizó red. Segundo motor y API OCR: NOT TESTED.
