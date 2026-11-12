#!/bin/bash
cd "<ROOT>/data/raw/bdg2"
B=https://media.githubusercontent.com/media/buds-lab/building-data-genome-project-2/master/data
dl(){ curl -L --fail --retry 20 --retry-delay 15 --retry-all-errors -C - -o "$2" "$B/$1" ; }
dl metadata/metadata.csv metadata.csv
dl weather/weather.csv weather.csv
dl meters/cleaned/electricity_cleaned.csv electricity_cleaned.csv
dl meters/cleaned/chilledwater_cleaned.csv chilledwater_cleaned.csv
dl meters/raw/electricity.csv electricity.csv
echo ALLDONE
