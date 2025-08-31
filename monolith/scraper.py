import os
import time
import traceback
import json
from dotenv import load_dotenv
from selenium import webdriver
from google.cloud import pubsub_v1
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc

load_dotenv()

class JobRightScraper:
    def __init__(self):
        self.driver = None
        self.main_window = None
        self.job_urls = []
        
    def setup_driver(self):
        """Initialize Chrome driver with proper options for Docker"""
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--remote-debugging-port=9222")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        print("Initializing Chrome driver...")
        self.driver = uc.Chrome(options=options)
        self.main_window = self.driver.current_window_handle
        return True

    def login(self, email, password):
        """Login to JobRight"""
        try:
            print("Navigating to JobRight...")
            self.driver.get("https://jobright.ai/")
            
            # Click sign in button
            signin_btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='SIGN IN']"))
            )
            signin_btn.click()
            
            # Enter credentials
            email_field = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@id='basic_email']"))
            )
            password_field = self.driver.find_element(By.XPATH, "//input[@id='basic_password']")
            
            email_field.send_keys(email)
            password_field.send_keys(password)
            password_field.send_keys(Keys.RETURN)
            
            # Wait for login success
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.XPATH, "//span[text()='Profile']"))
            )
            print("✅ Login successful!")
            return True
            
        except Exception as e:
            print(f"❌ Login failed: {e}")
            self.driver.save_screenshot("/app/screenshots/login_failure.png")
            return False

    def switch_to_most_recent(self):
        """Switch job sorting to 'Most Recent'"""
        try:
            print("Switching to 'Most Recent' sorting...")
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'index_jobs-recommend-sorter__')]"))
            )
            dropdown.click()
            
            most_recent_option = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='ant-select-item-option-content' and text()='Most Recent']"))
            )
            most_recent_option.click()
            
            time.sleep(3)
            print("✅ Switched to 'Most Recent'")
            return True
            
        except Exception as e:
            print(f"❌ Could not switch to 'Most Recent': {e}")
            return False

    def load_jobs(self, target_count=150):
        """Scroll to load jobs until we reach target count"""
        print(f"Loading jobs until we have {target_count}...")
        job_card_selector = "//div[contains(@class, 'index_job-card-main__spahH')]"
        
        while True:
            job_cards = self.driver.find_elements(By.XPATH, job_card_selector)
            current_count = len(job_cards)
            
            print(f"Currently loaded: {current_count} jobs")
            
            if current_count >= target_count:
                break
                
            # Scroll to last card
            if job_cards:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                    job_cards[-1]
                )
                
            # Wait for loading spinner
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'ant-spin-spinning')]"))
                )
                WebDriverWait(self.driver, 15).until_not(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'ant-spin-spinning')]"))
                )
            except:
                time.sleep(3)
                
            # Check if no new jobs loaded
            if len(self.driver.find_elements(By.XPATH, job_card_selector)) == current_count:
                print("No more jobs loading. Reached end of list.")
                break
                
        final_count = len(self.driver.find_elements(By.XPATH, job_card_selector))
        print(f"✅ Loaded {final_count} jobs total")
        return final_count

    def close_apply_modal(self):
        """Close the 'Did you apply?' modal using multiple strategies"""
        modal_closed = False
        
        # Strategy 1: Click "No, I didn't apply" button
        try:
            no_button = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'index_job-apply-confirm-popup-no-button__V7UbC')]"))
            )
            self.driver.execute_script("arguments[0].click();", no_button)
            print("✅ Clicked 'No, I didn't apply' button")
            modal_closed = True
        except:
            print("⚠️ Could not find 'No, I didn't apply' button")
        
        # Strategy 2: Click close button if "No" button didn't work
        if not modal_closed:
            try:
                close_button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Close']"))
                )
                self.driver.execute_script("arguments[0].click();", close_button)
                print("✅ Clicked close button")
                modal_closed = True
            except:
                print("⚠️ Could not find close button")
        
        # Strategy 3: Keyboard shortcut as fallback
        if not modal_closed:
            try:
                print("Trying keyboard shortcut: Tab + Tab + Tab + Enter")
                actions = ActionChains(self.driver)
                actions.send_keys(Keys.TAB).send_keys(Keys.TAB).send_keys(Keys.TAB).send_keys(Keys.ENTER).perform()
                modal_closed = True
            except:
                print("⚠️ Keyboard shortcut failed")
        
        # Strategy 4: ESC key as last resort
        if not modal_closed:
            try:
                print("Trying ESC key")
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                modal_closed = True
            except:
                print("❌ All modal closing strategies failed")
        
        time.sleep(2)  # Give modal time to close
        return modal_closed

    def process_job_card(self, card_index):
        """Process a single job card to extract URL with detailed logging"""
        try:
            # Get all current job cards
            job_cards = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'index_job-card-main__spahH')]")

            if card_index >= len(job_cards):
                print(f"❌ Card #{card_index + 1} not found")
                return None

            current_card = job_cards[card_index]

            # Scroll to card
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", 
                current_card
            )
            time.sleep(2)
            print(f"📍 Scrolled to card #{card_index + 1}")

            # Find apply button with more detailed logging
            try:
                apply_button = WebDriverWait(current_card, 10).until(
                    EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class, 'index_apply-button__kp79C')]"))
                )
                print(f"🔘 Found apply button for card #{card_index + 1}")
            except Exception as e:
                print(f"❌ Could not find apply button for card #{card_index + 1}: {e}")

                # Try alternative apply button selectors
                try:
                    apply_button = current_card.find_element(By.XPATH, ".//button[contains(text(), 'Apply')]")
                    print(f"🔘 Found apply button with alternative selector")
                except:
                    print(f"❌ No apply button found with any selector")
                    return None

            # Click apply button
            try:
                initial_windows = len(self.driver.window_handles)
                print(f"🪟 Current windows: {initial_windows}")
    
                # Method 1: Hover first, then real click
                try:
                    actions = ActionChains(self.driver)
                    actions.move_to_element(apply_button).pause(0.5).click().perform()
                    print(f"👆 Used ActionChains click for card #{card_index + 1}")
                except:
                    # Method 2: JavaScript click as fallback
                    self.driver.execute_script("arguments[0].click();", apply_button)
                    print(f"👆 Used JavaScript click for card #{card_index + 1}")
    
                # Wait for new window with better detection
                try:
                    # Wait a bit longer and check multiple times
                    for attempt in range(10):  # 10 attempts = 10 seconds
                        current_windows = len(self.driver.window_handles)
                        print(f"🪟 Attempt {attempt + 1}: {current_windows} windows")
                        
                        if current_windows > initial_windows:
                            print(f"🪟 New window detected after {attempt + 1} seconds!")
                            break
                            
                        time.sleep(1)
                    else:
                        print(f"❌ No new window opened after 10 seconds")
                        
                        # Debug: Check if button is actually clickable
                        print(f"🔍 Button enabled: {apply_button.is_enabled()}")
                        print(f"🔍 Button displayed: {apply_button.is_displayed()}")
                        
                        # Try clicking the button text/span instead
                        try:
                            button_text = apply_button.find_element(By.TAG_NAME, "span")
                            ActionChains(self.driver).move_to_element(button_text).click().perform()
                            print(f"👆 Clicked button text as backup")
                            
                            # Wait again
                            WebDriverWait(self.driver, 5).until(lambda d: len(d.window_handles) > initial_windows)
                            print(f"🪟 New window opened with button text click!")
                        except:
                            print(f"❌ Button text click also failed")
                            return None
                            
                except Exception as e:
                    print(f"❌ Error waiting for new window: {e}")
                    return None

            except Exception as e:
                print(f"❌ Error clicking apply button: {e}")
                return None

            # Switch to new window
            new_window = [w for w in self.driver.window_handles if w != self.main_window][0]
            self.driver.switch_to.window(new_window)

            # Get URL and close window
            time.sleep(3)
            job_url = self.driver.current_url
            print(f"🔗 Got URL: {job_url}")
            self.driver.close()

            # Switch back to main window
            self.driver.switch_to.window(self.main_window)

            # Handle the modal
            time.sleep(2)
            self.close_apply_modal()

            # Only return external URLs
            if "jobright.ai" not in job_url:
                print(f"✅ Card #{card_index + 1}: {job_url}")
                return job_url
            else:
                print(f"⚠️ Card #{card_index + 1}: Internal URL, skipping")
                return None

        except Exception as e:
            print(f"❌ Unexpected error processing card #{card_index + 1}: {type(e).__name__}: {e}")
            # ... rest of cleanup code

    def scrape_jobs(self, max_jobs=150):
        """Main scraping function"""
        print(f"Starting to scrape up to {max_jobs} jobs...")
        
        job_cards = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'index_job-card-main__spahH')]")
        total_cards = min(len(job_cards), max_jobs)
        
        for i in range(total_cards):
            print(f"\n--- Processing job {i + 1}/{total_cards} ---")
            url = self.process_job_card(i)
            if url:
                self.job_urls.append(url)
                
        return self.job_urls

    def run(self):
        """Main execution flow"""
        try:
            # Setup
            if not self.setup_driver():
                return []
                
            # Get credentials
            email = os.environ.get("JOBRIGHT_EMAIL")
            password = os.environ.get("JOBRIGHT_PASSWORD")
            
            if not email or not password:
                print("❌ Missing credentials in environment variables")
                return []
            
            # Execute workflow
            if not self.login(email, password):
                return []
                
            if not self.switch_to_most_recent():
                return []
                
            self.load_jobs(150)
            urls = self.scrape_jobs(150)  # Process first 150 jobs

            return urls
            
        except Exception as e:
            print(f"❌ Fatal error: {e}")
            traceback.print_exc()
            return []
            
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    scraper = JobRightScraper()
    collected_urls = scraper.run()
    
    print(f"\n{'='*50}")
    print(f"SCRAPING COMPLETE")
    print(f"{'='*50}")
    print(f"Total URLs collected: {len(collected_urls)}")
    
    if collected_urls:
        GCP_PROJECT_ID = os.environ.get("GCLOUD_PROJECT")
        TOPIC_ID = "scraped-urls"
        
        if not GCP_PROJECT_ID:
            raise ValueError("GCLOUD_PROJECT environment variable not set.")

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(GCP_PROJECT_ID, TOPIC_ID)

        def chunk_list(data, num_chunks):
            k, m = divmod(len(data), num_chunks)
            return [data[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(num_chunks)]

        num_batches = 2  # Based on worker's max-instances
        url_batches = chunk_list(list(set(collected_urls)), num_batches)
        
        print(f"\n--- Publishing {len(collected_urls)} URLs in {num_batches} batches ---")
        
        for i, batch in enumerate(url_batches):
            if not batch: continue
            
            message_data = {"urls": batch}
            message_future = publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
            message_future.result() # Wait for the publish to complete
            print(f"🚀 Dispatched batch #{i+1} with {len(batch)} URLs.")
            
        print("✅ All URLs published successfully.")
    else:
        print("No URLs were collected.")