curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source $HOME/.cargo/env
rustc --version
pip install --upgrade pip

sudo apt update
sudo apt install libudev-dev

pkg-config --libs --cflags libudev


cd iota-sdk/bindings/python
python setup.py install
