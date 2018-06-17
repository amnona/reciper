# reciper
recipe reverse engineering using the nutritional values of ingredients

# Idea
given a set of nutritional values (i.e. total calories, fat, etc. for a food product we want the recipe for), and given the list of ingredients, reciper queries a nutritional database for each ingredient, and then solves a set of positive linear equations to find the combination of ingredients to give the nutritional values.

# Installation
```
conda create -n reciper matplotlib numpy scipy jupyter python=3.6
source activate reciper
pip install fatsecret
```

# running
```
reciper/reciper.py
```
