#!/bin/bash

# Output file name
output_file="file_list.txt"

# Function to print directory tree and files with dynamic headers
print_directory_tree() {
  {
    echo "Directory Structure and Files in ./app:"
    tree -F ./app
    echo -e "\nDetails of Files:"
    find ./app -type f -exec sh -c 'file="{}"; if [[ -n "$(file -b --mime-encoding "$file" | grep -i "binary")" ]]; then
      echo "Binary File: $file"; 
    else
      echo "___________"; 
      echo "Start of file: $file"; 
      cat "$file"; 
      echo "End of file: $file"; 
      echo "___________"; 
    fi' \;
  } > "$output_file"
}

# Execute the function
print_directory_tree

echo "Script finished. Output saved to $output_file"
