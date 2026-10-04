# 834-group1

## Documentation
`ReplicationPackageScript/` - scripts from the replication package
`scripts/` - our scripts, mostly for getting the dataset together


### Setup
1. clone firefox repo into root project directory (same location as this README) with: 
```git clone --no-checkout https://github.com/mozilla-firefox/firefox```
This may take a while, ~6Gb.

2. run data pipeline (python3 main.py) to generate dataset (WIP). This may also take a while since the requests to bugzilla are intentionally throttled.


