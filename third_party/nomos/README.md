# Nomos standalone

We use the nomos standalone binary to analyzle the license text for some package managers (pip, pib) in Ubuntu environment. The source codes for nomos standalone can be obtained the [fossology](https://github.com/fossology/fossology/tree/master/src/nomos/agent) github repository. We already updloaded the 'nomossa' binary in this directory. If it doesn't work, you can build a binary from the source codes only for nomos standalone that moved from the fossology repository.

## How to build
### 1.Install the requirements
```
$ sudo apt-get install libglib2.0-dev
$ sudo apt-get install libjson-c-dev
```
### 2. Make
```
$ cd agent
$ cd make
```
### 3. Generate
The 'nomossa' binary can be generated in agent directory.

## License
GPL-2.0
