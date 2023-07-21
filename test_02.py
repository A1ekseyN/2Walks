def parse_txt_file(file_path):
    items = []

    with open(file_path, 'r', encoding='utf-8') as file:  # Specify the encoding as 'utf-8'
        next(file)  # Skip the first line with column headers
        for line in file:
            parts = line.strip().split('|')
            group_name = parts[0].strip()
            item_name = parts[1].strip()
            type_id = int(parts[-1])

            item = {"group_name": group_name, "name": item_name, "id": type_id}
            items.append(item)

    return items

file_path = "Price_List.txt"  # Specify the path to your file
parsed_items = parse_txt_file(file_path)

for item in parsed_items:
    print(f'{item},')

