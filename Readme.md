
# mitmdump decoder

## Description

A helper script for mitmproxy to decode protobuf serialized requests and responses.
It is primarily intended to help in validating the IDLs for the protocol.
As a intereting diversion, it also parses the GetMapObjects responses into a geojson format file that can be viewed using the 'ui'.  The ui is completely clientside, so it should be hostable with any static file server (I use 'http-server').  I also found that the script interface can support Flask, so the ui should be availeble from a proxied host on http://events

## Dependencies

Foremost, I am not providing, nor do I expect the notes below to be, a step-by-step series of instructions.  This project is for those with existing MITM experience.

Python 2.7
Requires mitmproxy, protobuf>=3.0.0a3, geojson, numpy, requests-futures

## Installing

### Linux

```
git clone https://github.com/bettse/mitmdump_decoder.git

apt-get install python-pip python-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev

pip install numpy geojson protobuf>=3.0.0a3 mitmproxy requests-futures
```

### OS X

* Install protobuf>3 via Homebrew with `brew install --devel protobuf`
* If you have never used pip before, install it:
  * `curl -O https://bootstrap.pypa.io/get-pip.py`
  * `sudo python get-pip.py`
* Install the needed pip packages 
  * `sudo pip install numpy geojson protobuf>=3.0.0a3 mitmproxy requests-futures`

## Running

I'm going to assume you can get mitmdump or mitmproxy running on its own first.


`mitmdump -p 8888 -s decode.py --ignore '^(?!pgorelease\.nianticlabs\.com)'`

## Rebuild python classes

### Linux/OS X

```
cd idl; ls -1 *.proto | while read filename; do protoc --python_out ../protocol/ $filename; done
```

### Windows

```
cd idl; ls *.proto | ForEach-Object { Invoke-Expression "protoc --proto_path '$($_.DirectoryName)' --python_out ../protocol/ '$($_.FullName)'" }
```


## Rebuild descriptors

### Windows

```
cd idl; ls *.proto | ForEach-Object { Invoke-Expression "protoc --proto_path '$($_.DirectoryName)' -o ../descriptors/$($_.Name).desc '$($_.FullName)'" }
```
