Data and code for the paper "The False positive problem of automatic bot detection in social science research"
Authors: Adrian Rauchfleisch & Jonas Kaiser
Date created: 2020/03/31 (revised with appendix analysis 2020/10/07)
Contact information: adrian.rauchfleisch@gmail.com/ jkaiser@cyber.harvard.edu
The paper can be downloaded here: (url will be added later)

You have to use R to replicate the results of our study.
Open the code.R script and then load the file "data_botometer.RData"
The .RData-file has one data frame - data_botometer.
The data frame has 5 columns:
user.id_str: Twitter user id as string
date: date class - date when the score and cap were measured
type: to which data set the account belongs
cap.universal: numeric - the CAP universal score from Botometer
scores.universal: numeric - the universal score from Botometer

To replicate the results, run the code from the beginning of the script with the set.seed-function
Results will be the same for all R version 3.6 or higher

We have added an additional data set (data_botometer_add.rds) with additional code (code_additional.R).
You can replicate our analysis reported in the appendix of our paper.