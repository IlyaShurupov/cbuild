import os
import sys

if len(sys.argv) != 2:
    print("Usage: python count_cpp_lines.py <directory_path>")
    sys.exit(1)

directory = sys.argv[1]

# Create a dictionary to store the counts for each file
counts = {}
total_count = 0

# Loop through each file in the directory and its subdirectories, excluding the "ext" directory
for root, dirs, files in os.walk(directory):
    dirs[:] = [d for d in dirs if d != 'ext']  # Exclude the "ext" directory
    for filename in files:
        if filename.endswith('.cpp') or filename.endswith('.h'):
            # Count the non-empty lines in the file
            with open(os.path.join(root, filename), 'r') as f:
                count = 0
                for line in f:
                    if line.strip() != '':
                        count += 1
            counts[os.path.join(root, filename)] = count
            total_count += count

# Print the sorted table
print('{:<90}{}'.format('File Name', 'Non-Empty Lines'))
print('-' * 100)

for filename, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
    print('{:<90}{}'.format(filename, count))

print('-' * 100)
print("Total Lines: ", str(total_count), "\n")