#!/bin/bash

# ANSI color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

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

# Function to check if conda is installed
check_conda() {
    if ! command -v conda &> /dev/null; then
        print_error "conda is not installed or not in PATH"
        print_info "Please install conda first: https://docs.conda.io/projects/conda/en/latest/user-guide/install/"
        exit 1
    fi
}

# Function to validate YAML file
validate_yaml() {
    local yml_file=$1
    if [ ! -f "$yml_file" ]; then
        print_error "Environment file '$yml_file' not found"
        exit 1
    fi

    if ! grep -q "name:" "$yml_file"; then
        print_error "YAML file must specify an environment name"
        exit 1
    fi
}

# Function to create the conda environment
create_environment() {
    local yml_file=$1
    local env_name=$(grep "name:" "$yml_file" | head -n1 | cut -d: -f2 | tr -d '[:space:]')

    print_info "Creating conda environment '$env_name' from $yml_file..."

    # Check if environment already exists
    if conda env list | grep -q "^$env_name "; then
        read -p "Environment '$env_name' already exists. Do you want to update it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Updating existing environment..."
            conda env update -f "$yml_file" --prune
        else
            print_info "Operation cancelled"
            exit 0
        fi
    else
        # Create new environment
        conda env create -f "$yml_file"
    fi
}

# Function to install Pytorch for AI strategies
install_pytorch() {
  local yml_file=$1
  local env_name=$(grep "name:" "$yml_file" | head -n1 | cut -d: -f2 | tr -d '[:space:]')

  # Activate conda environment
  print_info "Activating conda environment '$env_name'..."
  eval "$(conda shell.bash hook)"
  if ! conda activate "$env_name"; then
      print_error "Failed to activate environment '$env_name'"
      exit 1
  fi

  print_success "Successfully activated environment '$env_name'"

  # Ask for user consent to install PyTorch
  read -p "Would you like to install PyTorch in this environment? (y/n): " consent

  if [[ $consent =~ ^[Yy]$ ]]; then
      print_info "Installing PyTorch..."

      # Check if CUDA is available
      if command -v nvidia-smi &> /dev/null; then
          print_info "CUDA detected. Installing PyTorch with CUDA support..."
          if conda install pytorch torchvision torchaudio pytorch-cuda -c pytorch -c nvidia -y; then
              print_success "PyTorch successfully installed with CUDA support!"
          else
              print_error "Failed to install PyTorch with CUDA support"
              exit 1
          fi
      else
          print_info "CUDA not detected. Installing CPU-only version of PyTorch..."
          if conda install pytorch torchvision torchaudio cpuonly -c pytorch -y; then
              print_success "PyTorch (CPU version) successfully installed!"
          else
              print_error "Failed to install PyTorch"
              exit 1
          fi
      fi

      # Verify installation
      print_info "Verifying PyTorch installation..."
      if python -c "import torch; print('PyTorch version:', torch.__version__)" &> /dev/null; then
          print_success "PyTorch verification successful!"
      else
          print_error "PyTorch verification failed"
          exit 1
      fi
  else
      print_info "PyTorch installation skipped."
  fi

  conda deactivate
}

# Function to display activation instructions
show_instructions() {
    local yml_file=$1
    local env_name=$(grep "name:" "$yml_file" | head -n1 | cut -d: -f2 | tr -d '[:space:]')

    print_success "Environment setup completed!"
    print_info "To activate the environment, run:"
    print_info "    conda activate $env_name"
    print_info "To deactivate the environment, run:"
    print_info "    conda deactivate"
}

# Main script execution
main() {
    # Set default YAML file if no argument is provided
    local yml_file=${1:-environment.yml}

    # Run checks and create environment
    check_conda
    validate_yaml "$yml_file"
    create_environment "$yml_file"
    install_pytorch "$yml_file"
    show_instructions "$yml_file"
}

# Execute main function
main "$@"