from requests import Session
from idex import login
from util import css_find, slugify
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from html2text import HTML2Text
from config import CAMPUS_IDS, HTML_PARSER, BASE_OUTPUT_DIR

def get_enrolled_courses(sess, sesskey):
    """Fetches enrolled courses using the Moodle AJAX endpoint."""
    url = ("https://campus.exactas.uba.ar/lib/ajax/service.php?sesskey="
           + sesskey
           + "&info=core_course_get_enrolled_courses_by_timeline_classification")

    json_request = [{"index":0,"methodname":"core_course_get_enrolled_courses_by_timeline_classification","args":{"offset":0,"limit":0,"classification":"all","sort":"fullname","customfieldname":"","customfieldvalue":""}}]
    res = sess.post(url, json=json_request)
    return res.json()

def convert_name(name, is_filename=True, default_name="untitled", extension=".md"):
    """Converts a string to a basic directory or filename component."""
    name = name.lower().replace(' ', '_')
    if not name:
        name = default_name
    if is_filename:
        return name + extension
    else:
        return name

def save_markdown_content(filepath, markdown_text):
    """Saves the markdown text to a file, assuming success."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    print(f"      -- Saved to: '{filepath}'")

if __name__ == "__main__":
    sess = Session()
    html_converter = HTML2Text(baseurl='')

    login(sess)

    # Assume fetching main page, finding link, and getting sesskey succeed
    res_main_page = sess.get("https://campus.exactas.uba.ar/my/courses.php")
    logout_a = css_find(res_main_page, ".logininfo a")[1]
    sesskey = logout_a.attrs['href'].split('sesskey=')[1]

    # Assume getting courses succeeds
    enrolled_courses_response = get_enrolled_courses(sess, sesskey)
    courses = enrolled_courses_response[0]['data']['courses']
    print(f"Found {len(courses)} enrolled courses.")

    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    print(f"Saving course data under base directory: '{BASE_OUTPUT_DIR}'")

    print("\n--- Saving Individual Course Content as Markdown ---")
    for i, course in enumerate(courses):
        course_id = course['id']
        course_name = course['shortname']
        course_url = course['viewurl']

        if course_id not in CAMPUS_IDS:
            print(f"skipping: {course_name}, {course_id}")
            continue

        print(f"\n[{i+1}/{len(courses)}] Processing Course: {course_name}")

        course_dirname = convert_name(course_name, is_filename=False)
        course_output_path = os.path.join(BASE_OUTPUT_DIR, course_dirname)
        os.makedirs(course_output_path, exist_ok=True)
        print(f"  - Course directory: '{course_output_path}'")

        # --- Assume main course page fetch and processing succeed ---
        main_course_page_res = sess.get(course_url)
        main_course_page_res.raise_for_status() # Keep this basic check for HTTP errors? Or remove too? Let's keep it for now.
        soup_main = BeautifulSoup(main_course_page_res.text, HTML_PARSER)

        tab_links = soup_main.select('ul.nav-tabs.format_onetopic-tabs li a')

        if not tab_links:
            print("    - No tabs found. Extracting content from main page as 'main.md'.")
            content_uls = soup_main.select('ul.onetopic')
            if content_uls:
                main_content_html = "\n".join(str(ul) for ul in content_uls)
                main_markdown = html_converter.handle(main_content_html)
            else:
                main_markdown = "*No 'ul.onetopic' content found on the main page.*\n"

            main_filepath = os.path.join(course_output_path, "main.md")
            save_markdown_content(main_filepath, f"# {course_name} - Main Content\n\n{main_markdown}")

        else:
            print(f"    - Found {len(tab_links)} sections/tabs.")
            is_first_tab = True
            for tab_index, tab_link in enumerate(tab_links):
                section_title = tab_link.get_text(strip=True)
                section_url = tab_link.get('href')
                section_url = urljoin(course_url, section_url)

                print(f"      - Processing section: '{section_title}'")

                # --- Assume section fetch and processing succeed ---
                section_res = sess.get(section_url)
                section_res.raise_for_status() # Keep basic HTTP check?
                soup_section = BeautifulSoup(section_res.text, HTML_PARSER)

                content_uls = soup_section.select('ul.onetopic')
                section_markdown = ""
                if content_uls:
                    section_html = "\n".join(str(ul) for ul in content_uls)
                    section_markdown = html_converter.handle(section_html)
                    print(f"        - Extracted {len(content_uls)} 'ul.onetopic' element(s).")
                else:
                    section_markdown = "*No 'ul.onetopic' content found in this section.*\n"
                    print("        - No 'ul.onetopic' content found.")

                if is_first_tab:
                    filename = "main.md"
                    file_title = f"{course_name} - {section_title} (Main)"
                    is_first_tab = False
                else:
                    filename = convert_name(section_title, is_filename=True, default_name=f"section_{tab_index}", extension=".md")
                    file_title = f"{course_name} - {section_title}"

                filepath = os.path.join(course_output_path, filename)
                full_markdown_content = f"# {file_title}\n\n{section_markdown}"
                save_markdown_content(filepath, full_markdown_content) # Assume saving succeeds, maybe a gen catch for when it fails idk

    print("\n--- Finished sucesfully ---")
