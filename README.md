<div align="center"><img height="200" width="260" src="https://github.com/deltachat-bot/deltaland/raw/master/images/banner.png"></div>
<h1 align="center">Deltaland</h1>

<!-- 
[![Latest Release](https://img.shields.io/pypi/v/deltaland.svg)](https://pypi.org/project/deltaland)
[![Supported Versions](https://img.shields.io/pypi/pyversions/deltaland.svg)](https://pypi.org/project/deltaland)
[![License](https://img.shields.io/pypi/l/deltaland.svg)](https://pypi.org/project/deltaland)
-->
[![CI](https://github.com/deltachat-bot/deltaland/actions/workflows/ci.yml/badge.svg)](https://github.com/deltachat-bot/deltaland/actions/workflows/ci.yml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Contributors](https://img.shields.io/github/contributors/deltachat-bot/deltaland.svg)](https://github.com/deltachat-bot/deltaland/graphs/contributors)

> MMO game bot for Delta Chat

## Install

To install, open your terminal and run:

```sh
pip install git+https://github.com/deltachat-bot/deltaland.git
```

### Installing deltachat-rpc-server

This program depends on a standalone Delta Chat RPC server `deltachat-rpc-server` program that must be
available in your `PATH`. For installation instructions check:
https://github.com/deltachat/deltachat-core-rust/tree/master/deltachat-rpc-server

## Usage

Configure the bot:

```sh
deltaland init bot@example.com PASSWORD
```

Start the bot:

```sh
deltaland serve
```

Run `deltaland --help` to see all available options.

## Credits

The images are adapted material from https://midjourney.com licensed under the Creative Commons Noncommercial 4.0 Attribution International License (the “Asset License” https://creativecommons.org/licenses/by-nc/4.0/legalcode)
