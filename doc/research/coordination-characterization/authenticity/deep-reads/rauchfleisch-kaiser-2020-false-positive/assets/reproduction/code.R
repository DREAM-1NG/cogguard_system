## ---------------------------
##
## "The False positive problem of automatic bot detection in social science research"
##
## Results of the paper can be reproduced with the code in this script and an R version 3.6 or higher
##
## Author: Adrian Rauchfleisch & Jonas Kaiser
##
## Date Created: 2020-03-31
##
## 
## Email: adrian.rauchfleisch@gmail.com
##
## ---------------------------
##
## Notes: This script works together with the data_botometer.RData file
##        Paper can be downloaded here: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3565233
##
## ---------------------------

# Preparing the data and functions ####
# as we work with random numbers in this script we have to set the seed of R‘s random number generator at the beginning
# An R version 3.6 or higher will produce the exact same numbers
# with a lower version some numbers reported here might be slightly different as set.seed is different.
set.seed(124)
# import the data
load(file="data_botometer.RData")
# these are the account types we have in our data
table(data_botometer$type)
# load the packages
library(PRROC)
library(dplyr)
library(plyr)
library(sjstats)
library(data.table)
library(ggplot2)
library(ggridges)
# we take the mean universal score for every account
score_universal <- ddply(data_botometer, "user.id_str", summarise, 
                         score=mean(scores.universal, na.rm = F),
                         type=type[1])

# we take the mean universal cap for every account
score_cap <- ddply(data_botometer, "user.id_str", summarise, 
                   score=mean(cap.universal, na.rm = F),
                   type=type[1])

# we create two functions to estimate our bootstrapped ci
# for the precission-recall curve
pr_bootstrap <- function(class_1, class_0, n) {
  pr_aucs <- vector(length = n)
  pb <- txtProgressBar(min = 0, max = n, style = 3)
  for(i in 1:n) {
    pr <- pr.curve( sample(class_1, replace = T), sample(class_0, replace = T), curve=F, sorted = F)
    pr_aucs[i] <- pr$auc.integral
    setTxtProgressBar(pb, i)
  }
  close(pb)
  pr_aucs
}


# for the roc
roc_bootstrap <- function(class_1, class_0, n) {
  roc_aucs <- vector(length = n)
  pb <- txtProgressBar(min = 0, max = n, style = 3)
  for(i in 1:n) {
    roc <- roc.curve( sample(class_1, replace = T), sample(class_0, replace = T), curve=F, sorted = F)
    roc_aucs[i] <- roc$auc
    setTxtProgressBar(pb, i)
  }
  close(pb)
  roc_aucs
}

# a function to create our weighted resamples
weighted_resample <- function(df, column, bot, human, weight_bot, weight_human, n) {
  df <- df[df[,column] %in% c(bot, human), ]
  df$weight <- NA
  df[df[,column] %in% bot,"weight"] <- weight_bot/sum(df[,column] %in% bot)
  df[df[,column] %in% human,"weight"] <- weight_human/sum(df[,column] %in% human) 
  sample_vector<- sample(1:nrow(df), size=n, prob=df$weight, replace = T)
  df[sample_vector, ]
}

# 1. Calculating all ROC and PR with bootstrapping and CI for scores universal ####
# It is still possible that some of the received CI are slightly different from the values reported in the paper if you use a different seed
# all ci 
roc_all <- roc.curve( score_universal[score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                      score_universal[!score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                      curve=T, sorted = F)
boot_ci(roc_bootstrap(score_universal[score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                            score_universal[!score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                            n=10000))
# 0.8405145 0.8642589

pr.curve( score_universal[score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
           score_universal[!score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
           curve=T, sorted = F)
boot_ci(pr_bootstrap(score_universal[score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                            score_universal[!score_universal$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                            n=10000)) 
# 0.7521398 0.7912474

# Varol et al. ci
roc_varol <- roc.curve( score_universal[score_universal$type == "varol_bot","score"], 
                      score_universal[score_universal$type == "varol_human","score"], 
                      curve=T, sorted = F)
boot_ci(roc_bootstrap(score_universal[score_universal$type == "varol_bot","score"], 
                                score_universal[score_universal$type == "varol_human","score"], # here we select the humans
                              n=10000))
# 0.8439758 0.8780382

pr.curve( score_universal[score_universal$type == "varol_bot","score"], 
          score_universal[score_universal$type == "varol_human","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_universal[score_universal$type == "varol_bot","score"], 
                              score_universal[score_universal$type == "varol_human","score"],
                            n=10000))
# 0.7338452 0.7919544

# US politicians with new bots ci 
roc_us <- roc.curve( score_universal[score_universal$type == "bot","score"], 
                     score_universal[score_universal$type == "politician_us","score"], 
                     curve=T, sorted = F)
boot_ci(roc_bootstrap(score_universal[score_universal$type == "bot","score"], 
                                score_universal[score_universal$type == "politician_us","score"], # here we select the humans
                                n=10000)) 
# 0.9171311 0.9446979

pr.curve( score_universal[score_universal$type == "bot","score"], 
          score_universal[score_universal$type == "politician_us","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_universal[score_universal$type == "bot","score"], 
                              score_universal[score_universal$type == "politician_us","score"],
                              n=10000)) 
# 0.953862 0.9719251

# German politicians with German bots ci
roc_german <- roc.curve( score_universal[score_universal$type == "ger_bot","score"], 
                         score_universal[score_universal$type == "politician_germany","score"], 
                         curve=T, sorted = F)
boot_ci(roc_bootstrap(score_universal[score_universal$type == "ger_bot","score"], 
                             score_universal[score_universal$type == "politician_germany","score"], # here we select the humans
                             n=10000)) 
# 0.6956095  0.831717

pr.curve( score_universal[score_universal$type == "ger_bot","score"], 
          score_universal[score_universal$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_universal[score_universal$type == "ger_bot","score"], 
                           score_universal[score_universal$type == "politician_germany","score"],
                           n=10000))
# 0.07001413 0.1377587

# German politicians with new bots ci
roc_german_new <- roc.curve( score_universal[score_universal$type == "bot","score"], 
                             score_universal[score_universal$type == "politician_germany","score"], 
                             curve=T, sorted = F)
boot_ci(roc_bootstrap(score_universal[score_universal$type == "bot","score"], 
                                  score_universal[score_universal$type == "politician_germany","score"], # here we select the humans
                                  n=10000)) 
# 0.7391592 0.7934192

pr.curve( score_universal[score_universal$type == "bot","score"], 
          score_universal[score_universal$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_universal[score_universal$type == "bot","score"], 
                            score_universal[score_universal$type == "politician_germany","score"],
                            n=10000)) 
# 0.7832818 0.8371902

# roc visualization
roc_german_new_df <- as.data.frame(roc_german_new$curve)
roc_german_new_df$data <- "German politicians and bots"
roc_german_df <- as.data.frame(roc_german$curve)
roc_german_df$data <- "German politicians and German bots"
roc_us_df <- as.data.frame(roc_us$curve)
roc_us_df$data <- "US politicians and bots"
roc_varol_df <- as.data.frame(roc_varol$curve)
roc_varol_df$data <- "Varol et al."
roc_all_df <- as.data.frame(roc_all$curve)
roc_all_df$data <- "all"

roc_df <- rbind(roc_all_df, roc_german_new_df, roc_german_df, roc_us_df, roc_varol_df)

# Figure 2
ggplot(data=roc_df, aes(x=V1, y=V2, colour=data)) + 
  geom_line() +
  geom_point() +
  theme_minimal() +
  labs(x="false positive rate", y="Sensitivity (true positive rate)")


# 2. create resampled data set and calculate again all ROC and PR for scores universal ####

# resample all CI
resample_all <- weighted_resample(df = score_universal, 
                                  column = "type", 
                                  bot = c("bot", "ger_bot", "varol_bot"), 
                                  human = c("politician_germany", "politician_us", "varol_human"), 
                                  weight_bot = .15,
                                  weight_human = .85,
                                  n = 100000)

roc.curve( resample_all[resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
           resample_all[!resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_all[resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                              resample_all[!resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                              n=10000))
# 0.8498517 0.8563011

pr.curve( resample_all[resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
          resample_all[!resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_all[resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                            resample_all[!resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                            n=10000))
# 0.4918277 0.5066412

# resample Varol et al. ci
resample_varol <- weighted_resample(df = score_universal, 
                                  column = "type", 
                                  bot = c("varol_bot"), 
                                  human = c("varol_human"), 
                                  weight_bot = .15,
                                  weight_human = .85,
                                  n = 100000)

roc.curve( resample_varol[resample_varol$type == "varol_bot","score"], 
           resample_varol[resample_varol$type == "varol_human","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_varol[resample_varol$type == "varol_bot","score"], 
                                resample_varol[resample_varol$type == "varol_human","score"], # here we select the humans
                                n=10000))
# 0.8589915 0.8655979

pr.curve( resample_varol[resample_varol$type == "varol_bot","score"], 
          resample_varol[resample_varol$type == "varol_human","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_varol[resample_varol$type == "varol_bot","score"], 
                              resample_varol[resample_varol$type == "varol_human","score"],
                              n=10000))
# 0.5781187 0.5934393

# resample US politicians with new bots ci
resample_us <- weighted_resample(df = score_universal, 
                                    column = "type", 
                                    bot = c("bot"), 
                                    human = c("politician_us"), 
                                    weight_bot = .15,
                                    weight_human = .85,
                                    n = 100000)

roc.curve( resample_us[resample_us$type == "bot","score"], 
           resample_us[resample_us$type == "politician_us","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_us[resample_us$type == "bot","score"], 
                             resample_us[resample_us$type == "politician_us","score"], # here we select the humans
                             n=10000))
# 0.9271711 0.9326457

pr.curve( resample_us[resample_us$type == "bot","score"], 
          resample_us[resample_us$type == "politician_us","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_us[resample_us$type == "bot","score"], 
                           resample_us[resample_us$type == "politician_us","score"],
                           n=10000))
# 0.7872955 0.7994868

# resample German politicians with German bots ci
resample_german <- weighted_resample(df = score_universal, 
                                 column = "type", 
                                 bot = c("ger_bot"), 
                                 human = c("politician_germany"), 
                                 weight_bot = .15,
                                 weight_human = .85,
                                 n = 100000)

roc.curve( resample_german[resample_german$type == "ger_bot","score"], 
           resample_german[resample_german$type == "politician_germany","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_german[resample_german$type == "ger_bot","score"], 
                              resample_german[resample_german$type == "politician_germany","score"], # here we select the humans
                              n=10000))
# 0.7615729 0.7681723

pr.curve( resample_german[resample_german$type == "ger_bot","score"], 
          resample_german[resample_german$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_german[resample_german$type == "ger_bot","score"], 
                 resample_german[resample_german$type == "politician_germany","score"],
                            n=10000))
# 0.2692887 0.2760663

# German politicians with new bots ci
resample_german_new <- weighted_resample(df = score_universal, 
                                     column = "type", 
                                     bot = c("bot"), 
                                     human = c("politician_germany"), 
                                     weight_bot = .15,
                                     weight_human = .85,
                                     n = 100000)

roc.curve( resample_german_new[resample_german_new$type == "bot","score"], 
           resample_german_new[resample_german_new$type == "politician_germany","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_german_new[resample_german_new$type == "bot","score"], 
                  resample_german_new[resample_german_new$type == "politician_germany","score"], # here we select the humans
                  n=10000))
# 0.7585529 0.7660692

pr.curve( resample_german_new[resample_german_new$type == "bot","score"], 
          resample_german_new[resample_german_new$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_german_new[resample_german_new$type == "bot","score"], 
                 resample_german_new[resample_german_new$type == "politician_germany","score"],
                 n=10000))
# 0.2980379 0.3076967


# 3. Calculating all ROC and PR with bootstrapping and CI for CAP universal ####


# all ci 
roc_all_cap <- roc.curve( score_cap[score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                          score_cap[!score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                          curve=T, sorted = F)
boot_ci(roc_bootstrap(score_cap[score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                  score_cap[!score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                  n=10000))
# 0.8456914 0.8691662

pr.curve( score_cap[score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
          score_cap[!score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_cap[score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                 score_cap[!score_cap$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                 n=10000)) 
# 0.7566081 0.7959686

# Varol et al. ci
roc_varol_cap <- roc.curve( score_cap[score_cap$type == "varol_bot","score"], 
                            score_cap[score_cap$type == "varol_human","score"], 
                            curve=T, sorted = F)
boot_ci(roc_bootstrap(score_cap[score_cap$type == "varol_bot","score"], 
                  score_cap[score_cap$type == "varol_human","score"], # here we select the humans
                  n=10000))
# 0.8438485 0.8772513

pr.curve( score_cap[score_cap$type == "varol_bot","score"], 
          score_cap[score_cap$type == "varol_human","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_cap[score_cap$type == "varol_bot","score"], 
                 score_cap[score_cap$type == "varol_human","score"],
                 n=10000))
# 0.7328475  0.791645

# US politicians with new bots ci 
roc_us_cap <- roc.curve( score_cap[score_cap$type == "bot","score"], 
                         score_cap[score_cap$type == "politician_us","score"], 
                         curve=T, sorted = F)
boot_ci(roc_bootstrap(score_cap[score_cap$type == "bot","score"], 
                  score_cap[score_cap$type == "politician_us","score"], # here we select the humans
                  n=10000)) 
# 0.9278702  0.953703

pr.curve( score_cap[score_cap$type == "bot","score"], 
          score_cap[score_cap$type == "politician_us","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_cap[score_cap$type == "bot","score"], 
                 score_cap[score_cap$type == "politician_us","score"],
                 n=10000)) 
# 0.958964  0.976545

# German politicians with German bots ci
roc_german_cap <- roc.curve( score_cap[score_cap$type == "ger_bot","score"], 
                             score_cap[score_cap$type == "politician_germany","score"], 
                             curve=T, sorted = F)
boot_ci(roc_bootstrap(score_cap[score_cap$type == "ger_bot","score"], 
                  score_cap[score_cap$type == "politician_germany","score"], # here we select the humans
                  n=10000)) 
# 0.6975965 0.8356389

pr.curve( score_cap[score_cap$type == "ger_bot","score"], 
          score_cap[score_cap$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_cap[score_cap$type == "ger_bot","score"], 
                 score_cap[score_cap$type == "politician_germany","score"],
                 n=10000))
# 0.0718375  0.139259

# German politicians with new bots ci
roc_german_new_cap  <- roc.curve( score_cap[score_cap$type == "bot","score"], 
                                  score_cap[score_cap$type == "politician_germany","score"], 
                                  curve=T, sorted = F)
boot_ci(roc_bootstrap(score_cap[score_cap$type == "bot","score"], 
                  score_cap[score_cap$type == "politician_germany","score"], # here we select the humans
                  n=10000)) 
# 0.7516178 0.8050209

pr.curve( score_cap[score_cap$type == "bot","score"], 
          score_cap[score_cap$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(score_cap[score_cap$type == "bot","score"], 
                 score_cap[score_cap$type == "politician_germany","score"],
                 n=10000)) 
# 0.7873755 0.8416991

# roc visualization
roc_german_new_df <- as.data.frame(roc_german_new_cap$curve)
roc_german_new_df$data <- "German politicians and bots"
roc_german_df <- as.data.frame(roc_german_cap$curve)
roc_german_df$data <- "German politicians and German bots"
roc_us_df <- as.data.frame(roc_us_cap$curve)
roc_us_df$data <- "US politicians and bots"
roc_varol_df <- as.data.frame(roc_varol_cap$curve)
roc_varol_df$data <- "Varol et al."
roc_all_df <- as.data.frame(roc_all_cap$curve)
roc_all_df$data <- "all"

roc_df_cap <- rbind(roc_all_df, roc_german_new_df, roc_german_df, roc_us_df, roc_varol_df)

# Figure 3
ggplot(data=roc_df_cap, aes(x=V1, y=V2, colour=data)) + 
  geom_line() +
  geom_point() +
  theme_minimal() +
  labs(x="false positive rate", y="Sensitivity (true positive rate)")

# 4. create resampled data set and calculate again all ROC and PR for CAP universal ####

# resample all CI
resample_cap_all <- weighted_resample(df = score_cap, 
                                      column = "type", 
                                      bot = c("bot", "ger_bot", "varol_bot"), 
                                      human = c("politician_germany", "politician_us", "varol_human"), 
                                      weight_bot = .15,
                                      weight_human = .85,
                                      n = 100000)

roc.curve( resample_cap_all[resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
           resample_cap_all[!resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_cap_all[resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                  resample_cap_all[!resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                  n=10000))
# 0.8562701 0.8626126

pr.curve( resample_cap_all[resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
          resample_cap_all[!resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_cap_all[resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the bots
                 resample_cap_all[!resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], # here we select the humans
                 n=10000))
# 0.5006859 0.5157711

# resample Varol et al. ci
resample_cap_varol <- weighted_resample(df = score_cap, 
                                        column = "type", 
                                        bot = c("varol_bot"), 
                                        human = c("varol_human"), 
                                        weight_bot = .15,
                                        weight_human = .85,
                                        n = 100000)

roc.curve( resample_cap_varol[resample_cap_varol$type == "varol_bot","score"], 
           resample_cap_varol[resample_cap_varol$type == "varol_human","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_cap_varol[resample_cap_varol$type == "varol_bot","score"], 
                  resample_cap_varol[resample_cap_varol$type == "varol_human","score"], # here we select the humans
                  n=10000))
# 0.8577603 0.8643451

pr.curve( resample_cap_varol[resample_cap_varol$type == "varol_bot","score"], 
          resample_cap_varol[resample_cap_varol$type == "varol_human","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_cap_varol[resample_cap_varol$type == "varol_bot","score"], 
                 resample_cap_varol[resample_cap_varol$type == "varol_human","score"],
                 n=10000))
# 0.5740949 0.5896104

# resample US politicians with new bots ci
resample_cap_us <- weighted_resample(df = score_cap, 
                                     column = "type", 
                                     bot = c("bot"), 
                                     human = c("politician_us"), 
                                     weight_bot = .15,
                                     weight_human = .85,
                                     n = 100000)

roc.curve( resample_cap_us[resample_cap_us$type == "bot","score"], 
           resample_cap_us[resample_cap_us$type == "politician_us","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_cap_us[resample_cap_us$type == "bot","score"], 
                  resample_cap_us[resample_cap_us$type == "politician_us","score"], # here we select the humans
                  n=10000))
# 0.9380431 0.9432085

pr.curve( resample_cap_us[resample_cap_us$type == "bot","score"], 
          resample_cap_us[resample_cap_us$type == "politician_us","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_cap_us[resample_cap_us$type == "bot","score"], 
                 resample_cap_us[resample_cap_us$type == "politician_us","score"],
                 n=10000))
# 0.8068887 0.8187726

# resample German politicians with German bots ci
resample_cap_german <- weighted_resample(df = score_cap, 
                                         column = "type", 
                                         bot = c("ger_bot"), 
                                         human = c("politician_germany"), 
                                         weight_bot = .15,
                                         weight_human = .85,
                                         n = 100000)

roc.curve( resample_cap_german[resample_cap_german$type == "ger_bot","score"], 
           resample_cap_german[resample_cap_german$type == "politician_germany","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_cap_german[resample_cap_german$type == "ger_bot","score"], 
                  resample_cap_german[resample_cap_german$type == "politician_germany","score"], # here we select the humans
                  n=10000))
# 0.7631231 0.7698812

pr.curve( resample_cap_german[resample_cap_german$type == "ger_bot","score"], 
          resample_cap_german[resample_cap_german$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_cap_german[resample_cap_german$type == "ger_bot","score"], 
                 resample_cap_german[resample_cap_german$type == "politician_germany","score"],
                 n=10000))
# 0.26755 0.2744438

# German politicians with new bots ci
resample_cap_german_new <- weighted_resample(df = score_cap, 
                                             column = "type", 
                                             bot = c("bot"), 
                                             human = c("politician_germany"), 
                                             weight_bot = .15,
                                             weight_human = .85,
                                             n = 100000)

roc.curve( resample_cap_german_new[resample_cap_german_new$type == "bot","score"], 
           resample_cap_german_new[resample_cap_german_new$type == "politician_germany","score"], 
           curve=T, sorted = F)
boot_ci(roc_bootstrap(resample_cap_german_new[resample_cap_german_new$type == "bot","score"], 
                  resample_cap_german_new[resample_cap_german_new$type == "politician_germany","score"], # here we select the humans
                  n=10000))
# 0.77371 0.7808971

pr.curve( resample_cap_german_new[resample_cap_german_new$type == "bot","score"], 
          resample_cap_german_new[resample_cap_german_new$type == "politician_germany","score"], 
          curve=T, sorted = F)
boot_ci(pr_bootstrap(resample_cap_german_new[resample_cap_german_new$type == "bot","score"], 
                 resample_cap_german_new[resample_cap_german_new$type == "politician_germany","score"],
                 n=10000))
# 0.299411 0.3087247

# 5. Analysis time ####
# 5 accounts have to be dropped as we only have one measurement for them


# now the SD over time universal
time_score <- ddply(data_botometer, "user.id_str", summarise, 
                    sd=sd(scores.universal, na.rm = T),
                    type=type[1])
# ddply(time_score, "type", summarise, grp.mean=mean(sd, na.rm = T))
# rename for plot
time_score[time_score$type == "bot","type"] <- "New bots"
time_score[time_score$type == "ger_bot","type"] <- "German bots"
time_score[time_score$type == "politician_germany","type"] <- "German politicians"
time_score[time_score$type == "politician_us","type"] <- "US politicians"
time_score[time_score$type == "varol_bot","type"] <- "Varol bots"
time_score[time_score$type == "varol_human","type"] <- "Varol humans"
# change order in factor
time_score$type <- factor(time_score$type, levels = c("New bots", "German bots", "German politicians", "US politicians", "Varol bots", "Varol humans"))

# Figure 6 universal scores
ggplot(time_score, aes(x=sd, y=type)) + 
  geom_density_ridges(scale = 1, alpha=.5, bandwidth = 0.015) + theme_ridges()  + labs(y="data set", x= "SD universal scores") + scale_x_continuous(limit=c(0,0.4))


# now the SD over time cap
time_cap <- ddply(data_botometer, "user.id_str", summarise, 
                  sd=sd(cap.universal, na.rm = T),
                  type=type[1])

ddply(time_cap, "type", summarise, grp.mean=mean(sd, na.rm = T))

time_cap[time_cap$type == "bot","type"] <- "New bots"
time_cap[time_cap$type == "ger_bot","type"] <- "German bots"
time_cap[time_cap$type == "politician_germany","type"] <- "German politicians"
time_cap[time_cap$type == "politician_us","type"] <- "US politicians"
time_cap[time_cap$type == "varol_bot","type"] <- "Varol bots"
time_cap[time_cap$type == "varol_human","type"] <- "Varol humans"

time_cap$type <- factor(time_cap$type, levels = c("New bots", "German bots", "German politicians", "US politicians", "Varol bots", "Varol humans"))

# Figure 6 cap scores
ggplot(time_cap, aes(x=sd, y=type)) + 
  geom_density_ridges(scale = 1, alpha=.5, bandwidth = 0.015) + theme_ridges()  + labs(y="data set", x= "SD CAP") + scale_x_continuous(limit=c(0,0.4))

# changing scores with thresholds
# check for the universal score
time_df <- data_botometer
time_df$time_norm <- time_df$scores.universal > .76

change_score <- ddply(time_df, "user.id_str", summarise, 
                      bot_change_score=length(unique(time_norm)),
                      type=type[1])
# 2 means the account was at least once a bot and once a human during the 3 months
prop.table(table(change_score$type, change_score$bot_change_score), margin=1)

# check for the the cap
time_df$time_norm <- time_df$cap.universal > .25
change_cap <- ddply(time_df, "user.id_str", summarise, 
                    bot_change_cap=length(unique(time_norm)),
                    type=type[1])
prop.table(table(change_cap$type, change_cap$bot_change_cap), margin=1)

# we calculate the same as above for different thresholds
# scores:
thresholds <- seq(0, 1, 0.05)
time_list <- list()
for(i in 1:length(thresholds) ) {
  time_df$time_norm <- time_df$scores.universal > thresholds[i]
  change_df <- ddply(time_df, "user.id_str", summarise, 
                     bot_change_score=length(unique(time_norm)),
                     type=type[1])
  time_list[[i]] <- as.data.frame( prop.table(table(change_df$type, change_df$bot_change_score), margin=1), stringsAsFactors = F)
  rm(change_df)
  message(i)
}

# add the thresholds 
for( i in 1:21 ) {
  time_list[[i]]$threshold <- thresholds[i]
}

# for 0 and 1 we want to have 0 caases with 2
time_list[[1]]$Freq <- 0
time_list[[1]]$Var2 <- 2
time_list[[21]]$Freq <- 0
time_list[[21]]$Var2 <- 2

time_df_time <- rbindlist(time_list)
time_df_time <- time_df_time[time_df_time$Var2 == 2, ]
colnames(time_df_time) <- c("dataset", "Var2", "percentage", "threshold")

# Figure 7 - left
ggplot() + geom_line(data=time_df_time, aes(x=threshold, y=percentage, colour=dataset), size=1.5) + 
  theme_minimal() + 
  scale_x_continuous(breaks = thresholds) + 
  scale_y_continuous(labels = scales::percent_format(), breaks = seq(0, 0.7, 0.1), limit=c(0,0.72)) +
  theme(text = element_text(size=15)) + 
  labs(x="threshold universal score")

# cap:
thresholds <- seq(0, 1, 0.05)
time_list <- list()
for(i in 1:length(thresholds) ) {
  time_df$time_norm <- time_df$cap.universal > thresholds[i]
  change_df <- ddply(time_df, "user.id_str", summarise, 
                     bot_change_score=length(unique(time_norm)),
                     type=type[1])
  time_list[[i]] <- as.data.frame( prop.table(table(change_df$type, change_df$bot_change_score), margin=1), stringsAsFactors = F)
  rm(change_df)
  message(i)
}

# add the thresholds 
for( i in 1:21 ) {
  time_list[[i]]$threshold <- thresholds[i]
}

# for 0 and 1 we want to have 0 caases with 2
time_list[[1]]$Freq <- 0
time_list[[1]]$Var2 <- 2
time_list[[21]]$Freq <- 0
time_list[[21]]$Var2 <- 2

time_df_cap<- rbindlist(time_list)
time_df_cap <- time_df_cap[time_df_cap$Var2 == 2, ]
colnames(time_df_cap) <- c("dataset", "Var2", "percentage", "threshold")

# Figure 7 - left
ggplot() + geom_line(data=time_df_cap, aes(x=threshold, y=percentage, colour=dataset), size=1.5) + 
  theme_minimal() + 
  scale_x_continuous(breaks = thresholds) + 
  scale_y_continuous(labels = scales::percent_format(), breaks = seq(0, 0.7, 0.1), limit=c(0,0.72)) +
  theme(text = element_text(size=15)) + 
  labs(x="threshold CAP")

# 6. create the resampled PR curves ####
# universal scores
pr_score_all <- pr.curve( resample_all[resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                          resample_all[!resample_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                          curve=T, sorted = F)[["curve"]]
pr_score_german <- pr.curve( resample_german_new[resample_german_new$type %in% c("bot"),"score"], 
                             resample_german_new[resample_german_new$type %in% c("politician_germany"),"score"], 
                          curve=T, sorted = F)[["curve"]]

pr_score_all <- as.data.frame(pr_score_all, stringsAsFactors = F)
colnames(pr_score_all) <- c("recall","precision","score")
pr_score_all$data <- "all"

pr_score_german <- as.data.frame(pr_score_german, stringsAsFactors = F)
colnames(pr_score_german) <- c("recall","precision","score")
pr_score_german$data <- "German politicians and bots"
pr_resample <- rbind(pr_score_all, pr_score_german)


# prepare the values for specific threshold
p_all <- pr_score_all[which.min(abs(pr_score_all$score - .76)), ]
p_german <- pr_score_german[which.min(abs(pr_score_german$score - .76)), ]
# Figure 4
ggplot(data=pr_resample) + geom_line(aes(x=recall, y=precision, colour=data), size=1) + theme_minimal() +
  annotate("point", x=c(p_all[1,1], p_german[1,1]), y=c(p_all[1,2], p_german[1,2]), colour = "black", size=3) +
  scale_y_continuous(limit=c(0,1))

# universal cap
pr_cap_all <- pr.curve( resample_cap_all[resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                        resample_cap_all[!resample_cap_all$type %in% c("bot", "ger_bot", "varol_bot"),"score"], 
                        curve=T, sorted = F)[["curve"]]
pr_cap_german <- pr.curve( resample_cap_german_new[resample_cap_german_new$type %in% c("bot"),"score"], 
                           resample_cap_german_new[resample_cap_german_new$type %in% c("politician_germany"),"score"], 
                           curve=T, sorted = F)[["curve"]]

pr_cap_all <- as.data.frame(pr_cap_all, stringsAsFactors = F)
colnames(pr_cap_all) <- c("recall","precision","score")
pr_cap_all$data <- "all"

pr_cap_german <- as.data.frame(pr_cap_german, stringsAsFactors = F)
colnames(pr_cap_german) <- c("recall","precision","score")
pr_cap_german$data <- "German politicians and bots"
pr_resample <- rbind(pr_cap_all, pr_cap_german)

# prepare the values for specific threshold
p_cap_all <- pr_cap_all[which.min(abs(pr_cap_all$score - .25)), ]
p_cap_german <- pr_cap_german[which.min(abs(pr_cap_german$score - .25)), ]
# Figure 5
ggplot(data=pr_resample) + geom_line(aes(x=recall, y=precision, colour=data), size=1) + theme_minimal() +
  annotate("point", x=c(p_cap_all[1,1], p_cap_german[1,1]), y=c(p_cap_all[1,2], p_cap_german[1,2]), colour = "black", size=3) +
  scale_y_continuous(limit=c(0,1))

# 7. Density plots for the universal scores ####
# all combined data sets
density_plot_scores <- data.frame(score=c(resample_all$score, 
                                             resample_german$score, 
                                             resample_varol$score, 
                                             resample_german_new$score,
                                             resample_us$score),
                                     dateset=c(rep("all", 100000), 
                                               rep("German politicians and German bots", 100000), 
                                               rep("Varol et al.", 100000), 
                                               rep("German politicians and bots", 100000),
                                               rep("US politicians and bots", 100000)),
                                     stringsAsFactors=F)
# Figure 8 - left
ggplot(density_plot_scores, aes(x=score, y=dateset)) + 
  geom_density_ridges(scale = 1, alpha=.5, bandwidth = 0.04, quantiles = 2, quantile_lines = TRUE) + 
  theme_ridges() + 
  labs(y="data set", x= "unversal score") + 
  scale_x_continuous(limit=c(0,1))

# only human accounts
density_plot_humans <- data.frame(score=c(score_universal$score[score_universal$type %in% c("politician_germany", "politician_us", "varol_human")], 
                                                     score_universal$score[score_universal$type %in% c("politician_germany")], 
                                                     score_universal$score[score_universal$type == "varol_human"], 
                                                     score_universal$score[score_universal$type == "politician_us"]),
                                             dateset=c(rep("all humans", sum(score_universal$type %in% c("politician_germany", "politician_us", "varol_human"))), 
                                                       rep("German politicians", sum(score_universal$type %in% c("politician_germany"))), 
                                                       rep("Varol humans", sum(score_universal$type == "varol_human")), 
                                                       rep("US politicians", sum(score_universal$type == "politician_us")) ),
                                             stringsAsFactors=F)
                                  
# Figure 8 - right
ggplot(density_plot_humans, aes(x=score, y=dateset)) + 
  geom_density_ridges(scale = 1, alpha=.5, bandwidth = 0.04, quantiles = 2, quantile_lines = TRUE) + 
  theme_ridges()  + 
  labs(y="data set", x= "unversal score") +
  scale_x_continuous(limit=c(0,1))

# 8. DeLong test ####
library(pROC)
roc_us_delong <- roc(controls=sort(score_universal[score_universal$type %in% c("politician_us"),"score"]), 
                     cases=sort(score_universal[score_universal$type %in% c("bot"),"score"]))
roc_germany_delong <- roc(controls=sort(score_universal[score_universal$type %in% c("politician_germany"),"score"]), 
                          cases=sort(score_universal[score_universal$type %in% c("ger_bot"),"score"]))
roc_germanynew_delong<- roc(controls=sort(score_universal[score_universal$type %in% c("politician_germany"),"score"]), 
                            cases=sort(score_universal[score_universal$type %in% c("bot"),"score"]))

roc.test(roc_germany_delong, roc_us_delong, paired = FALSE)
roc.test(roc_germanynew_delong, roc_us_delong, paired = FALSE)

roc_us_delong <- roc(controls=sort(score_cap[score_cap$type %in% c("politician_us"),"score"]), 
                     cases=sort(score_cap[score_cap$type %in% c("bot"),"score"]))
roc_germany_delong <- roc(controls=sort(score_cap[score_cap$type %in% c("politician_germany"),"score"]), 
                          cases=sort(score_cap[score_cap$type %in% c("ger_bot"),"score"]))
roc_germanynew_delong<- roc(controls=sort(score_cap[score_cap$type %in% c("politician_germany"),"score"]), 
                            cases=sort(score_cap[score_cap$type %in% c("bot"),"score"]))

roc.test(roc_germany_delong, roc_us_delong, paired = FALSE)
roc.test(roc_germanynew_delong, roc_us_delong, paired = FALSE)
