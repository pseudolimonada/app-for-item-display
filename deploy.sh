#!/bin/bash

# Create .nojekyll file to prevent Jekyll processing
touch .nojekyll

# Add all changes
git add .

# Commit changes
git commit -m "deploy"

# Delete the gh-pages branch locally and remotely
git branch -D gh-pages || true
git push origin --delete gh-pages || true

# Create a new gh-pages branch from current state
git checkout -b gh-pages

# Push forcefully to gh-pages
git push -f origin gh-pages

# Return to previous branch
git checkout -

echo "Deployment complete. Give GitHub a few minutes to update the Pages site."
