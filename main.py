import os
import time
import traceback
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains # New import
import undetected_chromedriver as uc

load_dotenv()

def login_to_jobright(driver, email, password):
    # This function remains the same
    try:
        print("Navigating to jobright.ai to log in...")
        driver.get("https://jobright.ai/")
        main_signin_button_selector = "//span[text()='SIGN IN']"
        main_signin_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, main_signin_button_selector))
        )
        main_signin_button.click()
        print("Login modal opened.")
        email_field_selector = "//input[@id='basic_email']"
        password_field_selector = "//input[@id='basic_password']"
        email_input = WebDriverWait(driver, 10).until(
            EC.visibility_of_element_located((By.XPATH, email_field_selector))
        )
        password_input = driver.find_element(By.XPATH, password_field_selector)
        print("Entering credentials...")
        email_input.send_keys(email)
        password_input.send_keys(password)
        print("Submitting form by pressing Enter...")
        password_input.send_keys(Keys.RETURN)
        dashboard_element_selector = "//span[text()='Profile']"
        print("Waiting for dashboard to load...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, dashboard_element_selector))
        )
        print("Login successful! Dashboard loaded.")
        return True
    except Exception as e:
        print(f"An error occurred during login:")
        driver.save_screenshot("/app/screenshots/login_failure.png")
        print("Screenshot of failure saved to the 'screenshots' folder.")
        print(traceback.format_exc())
        return False

def switch_to_most_recent(driver):
    # This function remains the same
    try:
        print("Switching to 'Most Recent' jobs...")
        dropdown_selector = "//div[contains(@class, 'index_jobs-recommend-sorter__')]"
        dropdown = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, dropdown_selector))
        )
        dropdown.click()
        most_recent_option_selector = "//div[@class='ant-select-item-option-content' and text()='Most Recent']"
        most_recent_option = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, most_recent_option_selector))
        )
        most_recent_option.click()
        print("Successfully switched to 'Most Recent'.")
        time.sleep(3)
        return True
    except Exception as e:
        print(f"Could not switch to 'Most Recent' jobs. Error: {e}")
        return False

def scrape_job_links(driver):
    """
    Scrolls down, then processes cards, dismissing the modal
    with the Escape key for gentle error recovery.
    """
    final_urls = []
    
    # Scrolling logic remains the same
    print("\n--- Scrolling down to load all jobs ---")
    job_card_selector = "//div[contains(@class, 'index_job-card-main__spahH')]"
    
    while len(driver.find_elements(By.XPATH, job_card_selector)) < 150:
        job_cards = driver.find_elements(By.XPATH, job_card_selector)
        current_job_count = len(job_cards)
        print(f"Currently found {current_job_count} jobs. Scrolling to load more...")
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", job_cards[-1])
        
        try:
            spinner_selector = "//div[contains(@class, 'ant-spin-spinning')]"
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, spinner_selector)))
            WebDriverWait(driver, 20).until_not(EC.presence_of_element_located((By.XPATH, spinner_selector)))
        except:
            time.sleep(4)

        if len(driver.find_elements(By.XPATH, job_card_selector)) == current_job_count:
            print("No new jobs loaded. Reached the end of the list.")
            break
            
    print(f"\nFinished scrolling. Found a total of {len(driver.find_elements(By.XPATH, job_card_selector))} jobs.")
    
    initial_job_count = len(driver.find_elements(By.XPATH, job_card_selector))
    main_window = driver.current_window_handle
    apply_button_selector = ".//button[contains(@class, 'index_apply-button__kp79C')]"
    close_modal_button_selector = "//button[@aria-label='Close']"
    
    for i in range(initial_job_count):
        try:
            all_cards_on_page = driver.find_elements(By.XPATH, job_card_selector)
            current_card = all_cards_on_page[i]

            # Scroll to the card to make sure it's in view before interacting
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", current_card)
            time.sleep(1) # Give scroll a moment to settle
            
            apply_button = WebDriverWait(current_card, 10).until(
                EC.element_to_be_clickable((By.XPATH, apply_button_selector))
            )
            driver.execute_script("arguments[0].click();", apply_button)
            
            WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
            new_window = [w for w in driver.window_handles if w != main_window][0]
            driver.switch_to.window(new_window)
            
            time.sleep(3)
            final_url = driver.current_url
            
            if "jobright.ai" not in final_url:
                print(f"  -> Captured final URL for card #{i+1}: {final_url}")
                final_urls.append(final_url)
            
            driver.close()
            driver.switch_to.window(main_window)
            
            close_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, close_modal_button_selector))
            )
            driver.execute_script("arguments[0].click();", close_button)
            time.sleep(2)

        except Exception as e:
            print(f"  -> Could not process job card #{i+1}. Error: {type(e).__name__}")
            screenshot_path = f"/app/screenshots/card_failure_{i+1}.png"
            driver.save_screenshot(screenshot_path)
            print(f"     Screenshot saved. Attempting to recover by pressing ESCAPE.")
            
            # --- START OF GENTLE ERROR RECOVERY ---
            # Instead of refreshing, we send the ESCAPE key to close any modal
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(2) # Give modal time to close
            # --- END OF GENTLE ERROR RECOVERY ---
            
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(main_window)
            continue
            
    print("\nFinished scraping.")
    return final_urls


if __name__ == "__main__":
    options = uc.ChromeOptions()
    # For debugging, it can be helpful to run with a visible browser
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")


    print("Initializing undetected chromedriver...")
    driver = uc.Chrome(options=options, use_subprocess=False)

    email = os.environ.get("JOBRIGHT_EMAIL")
    password = os.environ.get("JOBRIGHT_PASSWORD")

    if not email or not password:
        print("Error: JOBRIGHT_EMAIL and JOBRIGHT_PASSWORD must be set in the .env file.")
    else:
        if login_to_jobright(driver, email, password):
            if switch_to_most_recent(driver):
                collected_urls = scrape_job_links(driver)
                print("\n--- All Collected URLs ---")
                for url in sorted(list(set(collected_urls))):
                    print(url)

    print("\nAll tasks complete. Closing browser.")
    driver.quit()