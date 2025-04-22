#!/bin/bash

# Create .nojekyll file to prevent Jekyll processing
touch .nojekyll

# Add all changes
git add .

# Commit changes
git commit -m "deploy"

# Push to gh-pages branch, forcing update
git push origin main:gh-pages --force
