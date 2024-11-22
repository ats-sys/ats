#!/bin/bash

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print error messages in red
print_error() {
    printf "${RED}Error: %s${NC}\n" "$1" >&2
}

# Function to print success messages in green
print_success() {
    printf "${GREEN}%s${NC}\n" "$1"
}

# Function to print info messages in blue
print_info() {
    printf "${BLUE}%s${NC}\n" "$1"
}

# Check if conda is installed
if ! command -v conda &> /dev/null; then
    print_error "conda is not installed. Please install Anaconda or Miniconda first."
    exit 1
fi

# Check if main.py exists in current directory
if [ ! -f "ats/main.py" ]; then
    print_error "ats/main.py not found in current directory."
    exit 1
fi

# Set environment name
env_name=ats

# Check if environment exists
if ! conda env list | grep -q "^${env_name}\s"; then
    print_error "Environment '$env_name' does not exist."
    exit 1
fi

# Activate conda environment
print_info "Activating conda environment '$env_name'..."
eval "$(conda shell.bash hook)"
if ! conda activate "$env_name"; then
    print_error "Failed to activate environment '$env_name'"
    exit 1
fi

print_success "Successfully activated environment '$env_name'"

# Run main.py
print_info "Starting the Program..."
if python -m ats.main; then
    print_success "Program executed successfully!"
else
    print_error "Error occurred while running main.py"
    conda deactivate
    exit 1
fi