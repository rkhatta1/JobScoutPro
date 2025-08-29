import os
import time
import traceback
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc

load_dotenv()

class JobRightScraper:
    """
    A robust, class-based scraper for Jobright.ai, designed to be used
    as a library by dispatcher and worker services.
    """
    def __init__(self):
        self.driver = None
        self.main_window = None

    def setup_driver(self):
        """Initializes a Chrome driver with stealth options."""
        try:
            options = uc.ChromeOptions()
            options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-blink-features=AutomationControlled")
            
            print("Initializing Chrome driver...")
            self.driver = uc.Chrome(options=options)
            self.main_window = self.driver.current_window_handle
            return True
        except Exception as e:
            print(f"❌ Failed to setup driver: {e}")
            return False

    def login(self, email, password):
        """Logs into Jobright.ai."""
        try:
            print("Navigating to JobRight...")
            self.driver.get("https://jobright.ai/")
            
            signin_btn = WebDriverWait(self.driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='SIGN IN']"))
            )
            ActionChains(self.driver).move_to_element(signin_btn).pause(0.5).click().perform()
            
            email_field = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@id='basic_email']"))
            )
            password_field = self.driver.find_element(By.XPATH, "//input[@id='basic_password']")
            
            email_field.send_keys(email)
            password_field.send_keys(password)
            password_field.send_keys(Keys.RETURN)
            
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
        """Switches the job sorting filter to 'Most Recent'."""
        try:
            print("Switching to 'Most Recent' sorting...")
            dropdown = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[contains(@class, 'index_jobs-recommend-sorter__')]"))
            )
            ActionChains(self.driver).move_to_element(dropdown).pause(0.5).click().perform()
            
            most_recent_option = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//div[@class='ant-select-item-option-content' and text()='Most Recent']"))
            )
            ActionChains(self.driver).move_to_element(most_recent_option).pause(0.5).click().perform()
            
            time.sleep(3)
            print("✅ Switched to 'Most Recent'")
            return True
            
        except Exception as e:
            print(f"❌ Could not switch to 'Most Recent': {e}")
            return False

    def load_jobs(self, target_count=150):
        """Scrolls down the page to load all job listings."""
        print(f"Loading jobs until we have approximately {target_count}...")
        job_card_selector = "//div[contains(@class, 'index_job-card-main__spahH')]"
        
        while True:
            job_cards = self.driver.find_elements(By.XPATH, job_card_selector)
            current_count = len(job_cards)
            
            if current_count >= target_count:
                break
                
            if not job_cards:
                print("No job cards found to begin scrolling.")
                break
                
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", job_cards[-1])
                
            try:
                WebDriverWait(self.driver, 3).until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'ant-spin-spinning')]")))
                WebDriverWait(self.driver, 15).until_not(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'ant-spin-spinning')]")))
            except:
                time.sleep(3)
                
            if len(self.driver.find_elements(By.XPATH, job_card_selector)) == current_count:
                print("No more jobs loading. Reached end of list.")
                break
                
        final_count = len(self.driver.find_elements(By.XPATH, job_card_selector))
        print(f"✅ Loaded {final_count} jobs total.")
        return final_count

    def close_apply_modal(self):
        """Closes the 'Did you apply?' modal using the ESC key."""
        try:
            # Wait for modal just in case, but primary action is ESC
            WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'index_job-apply-confirm-popup-content')]"))
            )
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(2)
        except:
            # If modal isn't found, that's okay, just continue
            pass

    def process_job_card(self, card_index):
        """Processes a single job card to extract the application URL."""
        try:
            job_cards = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'index_job-card-main__spahH')]")
            if card_index >= len(job_cards):
                return None

            current_card = job_cards[card_index]
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", current_card)
            time.sleep(1)

            apply_button = WebDriverWait(current_card, 10).until(
                EC.element_to_be_clickable((By.XPATH, ".//button[contains(@class, 'index_apply-button__kp79C')]"))
            )

            actions = ActionChains(self.driver)
            actions.move_to_element(apply_button).pause(0.5).click().perform()
            
            WebDriverWait(self.driver, 15).until(EC.number_of_windows_to_be(2))
            
            new_window = [w for w in self.driver.window_handles if w != self.main_window][0]
            self.driver.switch_to.window(new_window)
            
            time.sleep(3)
            job_url = self.driver.current_url
            self.driver.close()
            self.driver.switch_to.window(self.main_window)
            
            self.close_apply_modal()

            if "jobright.ai" not in job_url:
                print(f"✅ Card #{card_index + 1}: {job_url}")
                return job_url
            
        except Exception as e:
            print(f"❌ Unexpected error processing card #{card_index + 1}: {type(e).__name__}")
            if len(self.driver.window_handles) > 1:
                self.driver.close()
                self.driver.switch_to.window(self.main_window)
            self.close_apply_modal() # Try to close modal even on failure

        return None

    def scrape_job_batch(self, start_index, end_index):
        """Main scraping loop for a specific batch of jobs."""
        urls = []
        job_cards = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'index_job-card-main__spahH')]")
        total_available = len(job_cards)
        
        # Ensure end_index doesn't go out of bounds
        effective_end_index = min(end_index, total_available)

        for i in range(start_index, effective_end_index):
            print(f"\n--- Processing job {i + 1}/{total_available} ---")
            url = self.process_job_card(i)
            if url:
                urls.append(url)
        return urls

    def run_worker_task(self, start_index, end_index):
        """
        The complete, self-contained workflow for a single worker process.
        Returns a list of collected URLs.
        """
        urls = []
        try:
            if not self.setup_driver(): return []
            
            email = os.environ.get("JOBRIGHT_EMAIL")
            password = os.environ.get("JOBRIGHT_PASSWORD")
            
            if not email or not password:
                print("❌ Missing credentials in environment variables")
                return []
            
            if not self.login(email, password): return []
            if not self.switch_to_most_recent(): return []
            
            self.load_jobs(150)
            urls = self.scrape_job_batch(start_index, end_index)
            
        except Exception as e:
            print(f"❌ Fatal error in worker: {e}")
            traceback.print_exc()
        finally:
            if self.driver:
                self.driver.quit()
        
        return urls