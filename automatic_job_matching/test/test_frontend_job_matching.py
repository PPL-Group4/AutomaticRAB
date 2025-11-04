from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import tempfile
import time

class JobMatchingFrontEndTests(StaticLiveServerTestCase):
    def setUp(self):
        options = Options()
        options.add_argument("--headless=new")  
        options.add_argument("--no-sandbox")    
        options.add_argument("--disable-dev-shm-usage") 
        options.add_argument(f"--user-data-dir={tempfile.mkdtemp()}") 
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        self.browser = webdriver.Chrome(options=options)
        self.browser.implicitly_wait(3)

    def tearDown(self):
        self.browser.quit()

    def test_add_row_and_check_modal(self):
        self.browser.get(f"{self.live_server_url}/api/job-matching/")  # adjust URL if needed

        # Check that the initial table has one row
        rows = self.browser.find_elements(By.CSS_SELECTOR, "#jobRows tr")
        self.assertEqual(len(rows), 1)

        # Add a new row
        add_btn = self.browser.find_element(By.ID, "addRow")
        add_btn.click()
        time.sleep(0.5)

        rows = self.browser.find_elements(By.CSS_SELECTOR, "#jobRows tr")
        self.assertEqual(len(rows), 2)

    def test_open_review_modal(self):
        self.browser.get(f"{self.live_server_url}/api/job-matching/")
        self.browser.execute_script("""
        document.querySelector('.status-cell').innerHTML =
          '<button class="btn btn-sm btn-warning" id="testReviewBtn">Butuh Review</button>';
        document.getElementById('testReviewBtn').onclick = () => openReviewModal([{code:"A.1",name:"Galian Tanah"}], document.querySelector("#jobRows tr"));
        """)
        test_btn = self.browser.find_element(By.ID, "testReviewBtn")
        test_btn.click()
        time.sleep(0.5)

        modal = self.browser.find_element(By.ID, "reviewModal")
        self.assertTrue(modal.is_displayed())

    def test_check_codes_button_shows_spinner_and_status(self):
        self.browser.get(f"{self.live_server_url}/api/job-matching/")

        input_box = self.browser.find_element(By.CSS_SELECTOR, ".uraian-input")
        input_box.send_keys("pekerjaan beton")

        self.browser.execute_script("""
        window.fetch = async () => ({
            json: async () => ({status: "found", match: {code: "B.2", name: "Pekerjaan Beton"}})
        });
        """)

        check_btn = self.browser.find_element(By.ID, "checkCodes")
        check_btn.click()
        time.sleep(1)

        code_cell = self.browser.find_element(By.CSS_SELECTOR, ".match-code")
        status_btn = self.browser.find_element(By.CSS_SELECTOR, ".status-cell button")

        self.assertEqual(code_cell.text, "B.2")
        self.assertIn("Matched", status_btn.text)

    def test_save_review_updates_row(self):
        self.browser.get(f"{self.live_server_url}/api/job-matching/")
        self.browser.execute_script("""
        openReviewModal([{code:"A.5", name:"Pekerjaan Tanah"}], document.querySelector("#jobRows tr"));
        """)
        time.sleep(0.5)

        self.browser.find_element(By.CSS_SELECTOR, "input[name='matchChoice']").click()
        self.browser.find_element(By.ID, "saveReview").click()
        time.sleep(0.5)

        code_cell = self.browser.find_element(By.CSS_SELECTOR, ".match-code")
        status_btn = self.browser.find_element(By.CSS_SELECTOR, ".status-cell button")

        self.assertEqual(code_cell.text, "A.5")
        self.assertIn("Matched", status_btn.text)

    def test_manual_code_entry_updates_table(self):
        self.browser.get(f"{self.live_server_url}/api/job-matching/")
        self.browser.execute_script("openReviewModal([], document.querySelector('#jobRows tr'));")
        time.sleep(0.5)

        manual_input = self.browser.find_element(By.ID, "manualCode")
        manual_input.send_keys("C.7.2")
        self.browser.find_element(By.ID, "saveReview").click()
        time.sleep(0.5)

        code_cell = self.browser.find_element(By.CSS_SELECTOR, ".match-code")
        self.assertEqual(code_cell.text, "C.7.2")
