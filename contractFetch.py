"""
Author: swlee
Date: 2024.12.15

"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import csv
import datetime
import time
import json
import os

API_KEY = ""
API_URL = "https://api.etherscan.io/api"
MAX_PAGES = 10
DELAY = 2.0

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless') 
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920x1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
    
    return webdriver.Chrome(options=chrome_options)

def scrape_verified_contracts(start_page=1, max_pages=1):
    addresses = []
    driver = setup_driver()
    
    try:
        for page in range(1, max_pages + 1):
            url = f"https://etherscan.io/contractsVerified/{page}?ps=100"
            print(f"Scraping page {page}...")
            
            driver.get(url)
            time.sleep(DELAY)
            
            wait = WebDriverWait(driver, 10)
            table = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "table")))
            
            links = driver.find_elements(By.CSS_SELECTOR, "table.table tbody tr td:first-child a")
            
            for link in links:
                href = link.get_attribute('href')
                if href and 'address' in href:
                    addr = href.split('/address/')[-1].split('#')[0]
                    if addr.startswith('0x'):
                        addresses.append(addr)
                        print(f"Found address: {addr}")
            
            time.sleep(DELAY)
            
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
    
    finally:
        driver.quit()
        
    return addresses

def is_solidity_code(source_code):
    try:
        json.loads(source_code)
        return False
    except json.JSONDecodeError:
        return 'pragma solidity' in source_code or 'contract' in source_code

def clean_source_code(source_code):
    lines = source_code.splitlines()
    cleaned_lines = []
    
    pattern_lines = 0
    for i in range(min(24, len(lines))):
        line = lines[i].strip()
        # 줄이 "숫자 + 공백"으로 시작하는지 확인
        if line and line.split()[0].isdigit():
            pattern_lines += 1
    
    has_line_numbers = pattern_lines >= 20 
    
    for line in lines:
        if has_line_numbers:
            parts = line.strip().split(maxsplit=1)
            if parts and parts[0].isdigit():
                if len(parts) > 1:
                    cleaned_lines.append(parts[1])
            else:
                if line.strip():
                    cleaned_lines.append(line)
        else:
            if line.strip():
                cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def get_source_code(address):
    for attempt in range(3):
        try:
            driver = setup_driver()
            url = f"https://etherscan.io/address/{address}#code"
            
            driver.get(url)
            time.sleep(DELAY)
            
            source_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "editor"))
            )
            
            source_code = source_element.text
            
            source_code = clean_source_code(source_code)
            
            if not is_solidity_code(source_code):
                print(f"Skipping {address}: Not a Solidity file")
                return None
            
            try:
                contract_name_elements = driver.find_elements(By.CSS_SELECTOR, "div.d-flex.justify-content-between h6, div.h6.mb-3, .card-header .h6")
                contract_name = next((element.text for element in contract_name_elements if element.text), "Unknown Contract")
                
                filename = f"{address}_{contract_name}.sol"
                filename = "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.'))
                
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(source_code)
                print(f"Saved cleaned Solidity code to {filename}")
                
                return [{
                    'ContractAddress': address,
                    'ContractName': contract_name,
                    'SourceCode': source_code,
                    'SolFile': filename
                }]
            except Exception as e:
                print(f"Error saving contract: {e}")
                return None
            
        except Exception as e:
            print(f"Attempt {attempt+1} failed for {address}: {e}")
            if attempt < 2:
                time.sleep((attempt+1)*2)
        finally:
            driver.quit()
            
    print(f"All attempts failed for {address}")
    return None

def main():
   timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
   
   sol_dir = f"contracts_{timestamp}"
   os.makedirs(sol_dir, exist_ok=True)
   os.chdir(sol_dir) 
   
   csv_filename = f"VerifiedContractsSource-{timestamp}.csv"

   try:
       addresses = scrape_verified_contracts(MAX_PAGES)
       print(f"Collected {len(addresses)} addresses")

       with open(csv_filename, "w", newline='', encoding='utf-8') as csvfile:
           fieldnames = ['ContractAddress', 'ContractName', 'CompilerVersion', 'SourceCode', 'SolFile']
           writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
           writer.writeheader()

           for addr in addresses:
               print(f"Fetching source code for {addr}...")
               source_data = get_source_code(addr)
               time.sleep(DELAY)
               
               if not source_data:
                   continue

               for contract_info in source_data:
                   writer.writerow(contract_info)

       print(f"Done. Results saved to {csv_filename}")
       print(f"Contract source files saved in directory: {sol_dir}")

   except Exception as e:
       print(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    main()
