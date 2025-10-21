# `termradio` : a terminal-based radio player

A simple, bare-bones terminal-based radio player, with an opinionated set of default stations.  Lots of radio stations have streaming links that can be piped directly
into a media player. Keeping track of them and playing them in a
browser became cumbersome, so I wrote a little python program
`termradio` to play the radio from the terminal.

## usage

```{python}
python3 termradio.py SOMAGroove
```

If you make the script executable [`chmod +x termradio.py`], you can drop the extension and run

```
./termradio KEXP
```

If you store the script somewhere in your `$PATH` (e.g. `$HOME/.local/bin`), you can run `termradio <station>` from anywhere, or execute it as a background process from a launcher.

`termradio` accepts 1 argument, which is either a station name in
`stations.txt`, or a streaming url.

Stations live in a dictionary `stations.txt`, which is
pre-populated with a few stations I like (KEXP, KCRW, SOMAFM), and can
be added to by the user (please maintain valid python dict syntax). Send me pull requests (that double up as music recommendations, for once).


Play a random station:
```bash
python termradio.py
```

Play a specific station from `stations.txt`:
```bash
python termradio.py <station_name>
```
Example: `python termradio.py classic-rock-florida`

Play a stream from a URL:
```bash
python termradio.py <url>
```

## Supported Players

This script supports `mpv`, `mplayer`, and `vlc`. It will automatically detect which player you have installed. `mpv` is recommended.

## Installation of mpv

Here's how to install `mpv` on different operating systems.

### macOS (using Homebrew)

```bash
brew install mpv
```

### Ubuntu/Debian

```bash
sudo apt update
sudo apt install mpv
```

### Arch Linux

```bash
sudo pacman -Syu mpv
```

### Windows (using Scoop)

First, install [Scoop](https://scoop.sh/) if you don't have it. Then run:
```bash
scoop install mpv
```

