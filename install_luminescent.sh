# backend binaries
pip install gdown
apt-get install -y libglu1-mesa
gdown --fuzzy https://drive.google.com/file/d/1y9_HL5GPekKrxvpHzFGrqH8WXoeazMxx/view
tar -xf luminescent-latest.tar.gz  -C /usr/local/

export JULIA_CUDA_USE_COMPAT=0
export PATH=$PATH:/usr/local/Luminescent/bin

# first time run downloads artifacts
luminescent
