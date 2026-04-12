FROM balenalib/raspberrypi5-debian-python:3.11

RUN install_packages libportaudio2 python3-dev
RUN pip install sounddevice numpy requests

COPY koe-amp.py /usr/src/app/
WORKDIR /usr/src/app

CMD ["python3", "koe-amp.py"]
