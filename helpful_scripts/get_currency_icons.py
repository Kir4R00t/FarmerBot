import requests
import sys
import os

def main():
    if len(sys.argv) < 3:
        print('Usage: python get_currency_icons.py <path_to_folder> <poe2_scout_url>')
        sys.exit()
    
    # First validate if path to desired folder exists
    folder_path = sys.argv[1]
    if not os.path.isdir(folder_path): 
        print('Incorrect path to folder !')
        sys.exit()

    # Then handle the rqst itself
    url = sys.argv[2]
    r = requests.get(url)
    if r.status_code == 200:
        item_data = r.json()
    
        for item in item_data['items']:
            item_name = item['apiId']
            item_pic_url = item['iconUrl']

            item_pic_rqst = requests.get(item_pic_url)
            if item_pic_rqst.status_code == 200:
                full_path = os.path.join(folder_path, item_name)
                with open(full_path+'.png', 'wb') as file:
                    file.write(item_pic_rqst.content)
                
        print('Icons have been saved')
    
    else:
        print(f'Error code: {r.status_code}')
        sys.exit()

if __name__ == '__main__':
    main()
