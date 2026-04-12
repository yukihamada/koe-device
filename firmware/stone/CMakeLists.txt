cmake_minimum_required(VERSION 3.20.0)
find_package(Zephyr REQUIRED HINTS $ENV{ZEPHYR_BASE})
project(koe-stone VERSION 0.3.1)
target_sources(app PRIVATE src/main.c src/led.c src/tap.c src/ble_audio.c)
