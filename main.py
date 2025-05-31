from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import time
import re
from datetime import datetime, date
import csv
import pandas as pd
from autohubble import hubble_query_to_df_and_permalink, PRESTO

# Create CSV file 
csv_filename = "wire_recall_cases.csv"
csv_headers = ['Assignee', 'Date', 'Case Id', 'Front Link', 'Hubble Query', 'Details', 'Token_insert', 'Analysis', 'Response', 'Description']

service = Service()
driver = webdriver.Chrome(service=service)

def extract_vban(text):
    pattern = r'(?:4063-\d+|BNF:/(\d+)|PR WPIC:\s*(\d+))'
    match = re.search(pattern, text)
    return match.group(1) or match.group(2) or match.group(0) if match else None

def extract_amount(text):
    patterns = [
        r'Incoming Wire Amount:\s*USD\s*([\d,]+\.\d{2})',
        r'AMT:([\d,]+\.\d{2})\s*CUR:USD',
        r'AMT:([\d,]+\.\d{2})',
        r'Credit amount:\s*([\d,]+\.\d{2})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(',', ''))
    return None

def extract_trn(text):
    pattern = r'TRN:\s*(\d{6})-(\d{6})'
    match = re.search(pattern, text)
    return match.group(1) + match.group(2) if match else None

def extract_trace_number(text):
    pattern = r'Trace number:\s*(\d+)'
    match = re.search(pattern, text)
    return match.group(1) if match else None

def extract_date(text):
    patterns = [
        r'Incoming Wire Date:\s*(\d{1,2}/\d{1,2}/\d{4})',
        r'Effective date:\s*(\d{1,2}/\d{1,2}/\d{4})',
        r'SND DATE:\s*(\d{2}/\d{2}/\d{2})'
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            date_str = match.group(1)
            try:
                if len(date_str.split('/')[-1]) == 2:  # If the year is in YY format
                    return datetime.strptime(date_str, '%m/%d/%y').strftime('%Y-%m-%d')
                else:
                    return datetime.strptime(date_str, '%m/%d/%Y').strftime('%Y-%m-%d')
            except ValueError as e:
                print(f"Error parsing date: {str(e)} for date string: {date_str}")
    return None

def process_wire_text(text):
    return {
        'VBAN': extract_vban(text),
        'Amount': f"{extract_amount(text):.2f}" if extract_amount(text) is not None else None,
        'TRN': extract_trn(text),
        'Trace Number': extract_trace_number(text),
        'Date': extract_date(text)
    }

def generate_sql_query(extracted_info):
    sql_query = '''
    select
      valloc.external_id as customer,
      fnm.id as record_id,
      from_unixtime(
        fnm.funds_activity_event_data.arrived_at.millis / 1000
      ) as posting_date,
      fnm.funds_activity_event_data.amount.amount,
      vnm.ach.account_number as perfect_receivalbes_account_number,
      fnm.funds_activity_event_data.ach_event_data.sender_name,
      sba.account_number as stripe_bank_account_number,
      sle.legal_name as stripe_bank_account_name,
      vnm.merchant,
      intx.id,
      intx.source_id,
      cashwfpr.domestic.batch_header.originating_dfi_id || lpad(cashwfpr.domestic.entry.sequence_number, 7, '0') as trace_number
    from
      iceberg.cashreportingdb.wells_fargo_perfect_receivable_records cashwfpr
      right join iceberg.incomingtxndb.incoming_transaction_records intx on intx.source_id = cashwfpr.id
      right join iceberg.h_merchant_banktransfersfpi.sharded_funds_network_model_records fnm on fnm.incoming_transaction_id = intx.id
      left join iceberg.h_merchant_banktransfersfpi.sharded_vban_network_model_records vnm on fnm.funds_activity_event_data.external_id = vnm.id
      left join iceberg.h_merchant_banktransfersfpi.sharded_vban_allocation_model_records valloc on vnm.vban_allocation_id = valloc.id
      left join mongo.stripebankaccounts_default_locale sba on fnm.funds_activity_event_data.stripe_bank_account = sba._id
      left join mongo.stripelegalentities sle on sba.legal_entity = sle._id
    where
      vnm.ach.account_number = '{vban}' and fnm.funds_activity_event_data.amount.amount like '%{amount}%'
      and
      from_unixtime(
        fnm.funds_activity_event_data.arrived_at.millis / 1000
      ) = date'{date}'
    '''
    return sql_query.format(
        vban=extracted_info['VBAN'],
        amount=extracted_info['Amount'],
        date=extracted_info['Date']
    )

def save_to_csv(complete_wfw_text, text_to_paste, sql_query, response, analysis):
    try:
        # Check if the file exists, if not, create it and write the headers
        try:
            with open(csv_filename, 'x', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
                writer.writeheader()
        except FileExistsError:
            pass  # File already exists, we'll append to it

        # Prepare the row data
        row_data = {
            'Assignee': 'advikn',
            'Date': date.today().strftime('%Y-%m-%d'),
            'Case Id': complete_wfw_text,
            'Front Link': '',
            'Hubble Query': sql_query,
            'Details': text_to_paste,
            'Token_insert': '',
            'Analysis': analysis,
            'Response': response,
            'Description': ''
        }

        # Append the row to the CSV file
        with open(csv_filename, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writerow(row_data)

        print(f"Data has been appended to {csv_filename}")
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")

def add_internal_comment(driver, comment):
    try:
        internal_comment_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.XPATH, "//div[@class='commentComposer__StyledPlaceholderDiv-sc-49d64c4b-11 ceHJEJ' and text()='Add internal comment']"))
        )
        driver.execute_script("arguments[0].click();", internal_comment_button)
        print("Clicked on internal comment button")

        time.sleep(5)

        comment_box = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//div[@class='contentEditable__StyledDefaultContentEditable-sc-20431053-0 bXmNGY commentComposer__StyledContentEditable-sc-49d64c4b-8 grqmyj']"))
        )
        driver.execute_script("arguments[0].click();", comment_box)
        comment_box.send_keys(Keys.CONTROL, 'a')
        comment_box.send_keys(Keys.DELETE)
        for line in comment.split('\n'):
            comment_box.send_keys(line)
            comment_box.send_keys(Keys.SHIFT, Keys.ENTER)

        comment_box.send_keys(Keys.ENTER)
        print("Comment added to the internal comment")

        time.sleep(5)
    except Exception as e:
        print(f"Failed to add comment to internal comment: {str(e)}")

def process_case(driver):
    try:
        try:
            wfw_text = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'WFW')]"))
            ).text
            print(f"Extracted WFW text: {wfw_text}")
        except Exception as e:
            print(f"Error extracting WFW text: {str(e)}")
            body_element = driver.find_element(By.TAG_NAME, 'body')
            body_element.send_keys(Keys.ARROW_DOWN)
            print("Pressed the down arrow button")
            time.sleep(5)
            return True

        pattern = r'(WFW\d{6}-\d{6}.*?(?:Action Required:?|Wire Recall|ACH Recall).*?(?:SVW:\d+|$))'
        match = re.search(pattern, wfw_text, re.IGNORECASE | re.DOTALL)
        complete_wfw_text = match.group(1).strip() if match else "WFW text not found"

        time.sleep(5)

        try:
            open_message_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Open Message')]"))
            )
            open_message_button.click()
            time.sleep(10)
            driver.switch_to.window(driver.window_handles[-1])

            if len(driver.find_elements(By.ID, "password")) > 0:
                password_input = driver.find_element(By.ID, "password")
                password_input.send_keys("tBGUUb4UueBj58m3Yrkj")

                remember_me_checkbox = driver.find_element(By.ID, "remembermecheckbox")
                remember_me_checkbox.click()

                sign_in_button = driver.find_element(By.XPATH, "//input[@value='Sign In']")
                sign_in_button.click()

                time.sleep(15)

            all_text = driver.execute_script("""
                var body = document.body;
                var range = document.createRange();
                range.selectNodeContents(body);
                return range.toString();
            """)
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
        except Exception as e:
            print(f"Error opening message: {str(e)}")
            all_text = wfw_text  # Use the Front text if we can't open the message

        results = process_wire_text(all_text)
        if results:
            print("Extracted Information:")
            for key, value in results.items():
                print(f"{key}: {value}")

            print("\nGenerated SQL Query:")
            sql_query = generate_sql_query(results)
            try:
                permalink, df = hubble_query_to_df_and_permalink(sql_query, PRESTO)
                print(df)
                print(f"Permalink: {permalink}")
            except Exception as e:
                print(f"Error executing SQL query: {str(e)}")
                error_comment = "Needs investigation: Error executing Hubble query."
                add_internal_comment(driver, error_comment)
                save_to_csv(complete_wfw_text, "", sql_query, error_comment, "Needs Investigation")
                return True

            if not df.empty:
                cu_token = df['customer'].iloc[0]
                
                analysis = "**Analysis:** "
                analysis_points = []

                extracted_vban = results['VBAN'].strip() if results['VBAN'] else ''
                df_vban = str(df['perfect_receivalbes_account_number'].iloc[0]).strip()
                
                if extracted_vban == df_vban:
                    analysis_points.append("VBAN matches the Perfect Receivables Account Number")
                else:
                    analysis_points.append(f"VBAN does not match the Perfect Receivables Account Number. Extracted: {extracted_vban}, Hubble: {df_vban}")
                
                extracted_amount = results['Amount'].split('.')[0][:4] if results['Amount'] else ''
                df_amount = str(df['amount'].iloc[0]).split('.')[0][:4]
                if extracted_amount == df_amount:
                    analysis_points.append("First 4 digits of the Amount match")
                else:
                    analysis_points.append(f"First 4 digits of the Amount do not match. Extracted: {extracted_amount}, Hubble: {df_amount}")
                
                if results['Date'] == df['posting_date'].iloc[0].strftime('%Y-%m-%d'):
                    analysis_points.append("Date matches the Posting Date")
                else:
                    analysis_points.append(f"Date does not match the Posting Date. Extracted: {results['Date']}, Hubble: {df['posting_date'].iloc[0].strftime('%Y-%m-%d')}")
                
                if results['Trace Number'] == df['trace_number'].iloc[0]:
                    analysis_points.append("Trace Number matches")
                else:
                    analysis_points.append(f"Trace Number does not match. Extracted: {results['Trace Number']}, Hubble: {df['trace_number'].iloc[0]}")

                analysis += " ".join(analysis_points) + "\n"

                formatted_results = f"""
**Hubble Query Results:**
Customer: {cu_token}
Record ID: {df['record_id'].iloc[0]}
Posting Date: {df['posting_date'].iloc[0].strftime('%Y-%m-%d')}
Amount: {df['amount'].iloc[0]}
Perfect Receivables Account Number: {df['perfect_receivalbes_account_number'].iloc[0]}
Sender Name: {df['sender_name'].iloc[0]}
Stripe Bank Account Number: {df['stripe_bank_account_number'].iloc[0]}
Stripe Bank Account Name: {df['stripe_bank_account_name'].iloc[0]}
Merchant: {df['merchant'].iloc[0]}
ID: {df['id'].iloc[0]}
Source ID: {df['source_id'].iloc[0]}
Trace Number: {df['trace_number'].iloc[0]}
"""

                response = f"""
Hi Team,

Confirming that we reject the attempt to recall and do not grant debit authorization. In this case, we can confirm that the funds were received, and reconciled to the intended merchant, though they have not yet been applied to an invoice. However, since the merchant has access to these funds, we would encourage the account holder to reach out to them directly if they have any questions or wish to request a refund.
In case it's helpful, here is the customer reference number that the account holder can use to identify their payment when reaching out to the merchant: {cu_token}

**Extracted Information:**
VBAN: **{results['VBAN']}**
Amount: **{results['Amount']}**
TRN: **{results['TRN']}**
Trace Number: **{results['Trace Number']}**
Date: **{results['Date']}**

{analysis}

Best,
Stripe Team

**Hubble Query Permalink:**
{permalink}

{formatted_results}
"""
            else:
                response = f"""
Hi Team,

Not a horizon case, needs investigation.

**Extracted Information:**
VBAN: **{results['VBAN']}**
Amount: **{results['Amount']}**
TRN: **{results['TRN']}**
Trace Number: **{results['Trace Number']}**
Date: **{results['Date']}**

No results found in Hubble query.

**Hubble Query Permalink:**
{permalink}
"""
            print(response)
        else:
            print("No relevant information found in the text.")
            response = "No relevant information found in the text."

        text_to_paste = f"""
Front Email Information:
VBAN: **{results.get('VBAN', 'N/A')}**
Amount: **{results.get('Amount', 'N/A')}**
TRN: **{results.get('TRN', 'N/A')}**
Date: **{results.get('Date', 'N/A')}**

{formatted_results if 'formatted_results' in locals() else ''}
"""

        add_internal_comment(driver, response)

        save_to_csv(complete_wfw_text, text_to_paste, sql_query, response, analysis if 'analysis' in locals() else 'No analysis performed')

        body_element = driver.find_element(By.TAG_NAME, 'body')
        body_element.send_keys(Keys.ARROW_DOWN)
        print("Pressed the down arrow button")

        time.sleep(5)

    except Exception as e:
        print(f"Error: {str(e)}")

        text_to_paste = """
Front Email Information:
VBAN: **N/A**
Amount: **N/A**
TRN: **N/A**
Date: **N/A**
"""

        error_comment = "Needs investigation: An error occurred during processing."
        add_internal_comment(driver, error_comment)

        save_to_csv(complete_wfw_text if 'complete_wfw_text' in locals() else "WFW text not found", 
                    text_to_paste, 
                    '', 
                    error_comment, 
                    'Needs Investigation')

        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(driver.window_handles[0])

        body_element = driver.find_element(By.TAG_NAME, 'body')
        body_element.send_keys(Keys.ARROW_DOWN)
        print("Pressed the down arrow button")
        time.sleep(5)

    return True

# Main execution
driver.get("https://stripe-ops.frontapp.com/inboxes/teammates/3112259/assigned/open/0")

time.sleep(20)

while True:
    try:
        success = process_case(driver)
        if not success:
            print("Reached the end of tickets or encountered an error. Ending the process.")
            break
    except Exception as e:
        print(f"An error occurred in the main loop: {str(e)}")
        try:
            driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ARROW_DOWN)
            print("Pressed the down arrow button due to an error")
            time.sleep(5)
        except:
            print("Failed to move to next email after error. Exiting.")
            break

driver.quit()
