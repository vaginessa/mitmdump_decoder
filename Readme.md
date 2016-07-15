
# mitmdump deocder

## Description

A helper script for mitmproxy to decode protobuf serialized requests and responses.
It also parses the GetMapObjects responses into a geojson format file that can be viewed using the 'ui'.  The ui is completely clientside, so it should be hostable with any static file server (I use 'http-server').

## Dependencies

Python 2.7
Requires mitmproxy, protobuf>=3.0.0a3, geojson, numpy

## Installing

```
git clone https://github.com/bettse/mitmdump_decoder.git

apt-get install python-pip python-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev

pip install numpy geojson protobuf>=3.0.0a3 mitmproxy
```

## Running

`mitmdump -p 8888 -s decode.py "~d pgorelease.nianticlabs.com"`


## Rebuild python classes

### Linux

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
