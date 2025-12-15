from requests import Session
from idex import login
from util import css_find, slugify
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from html2text import HTML2Text
from config import CAMPUS_IDS, HTML_PARSER, BASE_OUTPUT_DIR, MOODLE_RESOURCE_PATHS
import mimetypes

def get_enrolled_courses(sess, sesskey):
    """Fetches enrolled courses using the Moodle AJAX endpoint."""
    url = ("https://campus.exactas.uba.ar/lib/ajax/service.php?sesskey="
           + sesskey
           + "&info=core_course_get_enrolled_courses_by_timeline_classification")

    json_request = [{"index":0,"methodname":"core_course_get_enrolled_courses_by_timeline_classification","args":{"offset":0,"limit":0,"classification":"all","sort":"fullname","customfieldname":"","customfieldvalue":""}}]
    res = sess.post(url, json=json_request)
    return res.json()

def convert_name(name, is_filename=True, default_name="untitled", extension=".md"):
    """Converts a string to a valid directory or filename component using slugify."""
    name = slugify(name) or default_name
    if is_filename:
        base, _ = os.path.splitext(name)
        return (base or name) + extension
    return name

def save_markdown_content(filepath, markdown_text):
    """Saves the markdown text to a file, assuming success."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    print(f"      -- Saved to: '{filepath}'")

def download_file(sess: Session, url: str, base_dir: str, filename: str):
    """Downloads a file from a URL into the specified base directory."""
    filepath = os.path.join(base_dir, filename)

    print(f"      -- Downloading: '{filename}' -> '{os.path.relpath(base_dir, BASE_OUTPUT_DIR)}'")
    response = sess.get(url, stream=True)

    # Check Content-Disposition for a better filename
    content_disposition = response.headers.get('content-disposition')
    if content_disposition:
        parts = content_disposition.split('filename=')
        if len(parts) > 1:
             header_filename_raw = parts[1].strip().strip('"\'')
             if header_filename_raw:
                 _, orig_ext = os.path.splitext(header_filename_raw)
                 header_filename_base = slugify(os.path.splitext(header_filename_raw)[0])
                 header_filename = (header_filename_base or slugify("downloaded_file")) + orig_ext
                 if header_filename:
                    filename = header_filename
                    filepath = os.path.join(base_dir, filename)

    os.makedirs(base_dir, exist_ok=True)
    with open(filepath, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"      -- Saved File: '{os.path.basename(filepath)}'")


def sanitize_filename(filename: str, default_name="downloaded_file") -> str:
    """Cleans a filename using slugify, preserving extension."""
    if not filename: return default_name
    base, ext = os.path.splitext(filename)
    sanitized_base = slugify(base)
    return (sanitized_base or default_name) + ext

def handle_folder_download(sess: Session, folder_url: str, base_dir: str, folder_name: str, processed_urls: set):
    """Handles downloading all files within a Moodle folder."""
    folder_slug = convert_name(folder_name, is_filename=False)
    folder_path = os.path.join(base_dir, folder_slug)
    os.makedirs(folder_path, exist_ok=True)
    
    print(f"        - Processing folder: '{folder_name}' -> '{os.path.relpath(folder_path, BASE_OUTPUT_DIR)}'")

    try:
        res = sess.get(folder_url)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, HTML_PARSER)

        # Find all file links within the folder view
        file_links = soup.select('span.fp-filename a')

        if not file_links:
            print(f"          - No files found in folder '{folder_name}'.")
            return

        print(f"          - Found {len(file_links)} files in folder.")
        for link in file_links:
            file_url = link.get('href')
            if not file_url or file_url.startswith('#'):
                continue

            absolute_file_url = urljoin(folder_url, file_url)
            if absolute_file_url in processed_urls:
                continue
            
            filename = sanitize_filename(link.get_text(strip=True))
            download_file(sess, absolute_file_url, folder_path, filename)
            processed_urls.add(absolute_file_url)

    except Exception as e:
        print(f"        - ERROR processing folder {folder_url}: {e}")

if __name__ == "__main__":
    sess = Session()
    html_converter = HTML2Text(baseurl='')

    login(sess)

    res_main_page = sess.get("https://campus.exactas.uba.ar/my/courses.php")
    logout_a = css_find(res_main_page, ".logininfo a")[1]
    sesskey = logout_a.attrs['href'].split('sesskey=')[1]

    enrolled_courses_response = get_enrolled_courses(sess, sesskey)
    courses = enrolled_courses_response[0]['data']['courses']
    print(f"Found {len(courses)} enrolled courses.")

    os.makedirs(BASE_OUTPUT_DIR, exist_ok=True)
    print(f"Saving course data under base directory: '{BASE_OUTPUT_DIR}'")

    enrolled_ids = set()
    for i, course in enumerate(courses):
        enrolled_ids.add(course['id'])

    for cfg_id in CAMPUS_IDS:
        if cfg_id not in enrolled_ids:
            print(f"Adding not enrolled but configured course (ID: {cfg_id})")
            courses.append(dict(
                id=cfg_id,
                shortname=f"curso {cfg_id}",
                viewurl=f"https://campus.exactas.uba.ar/course/view.php?id={cfg_id}",
            ))

    print("\n--- Processing Courses ---")
    for i, course in enumerate(courses):
        course_id, course_name, course_url = course['id'], course['shortname'], course['viewurl']

        if course_id not in CAMPUS_IDS:
            print(f"Skipping: {course_name} (ID: {course_id}) - Not in CAMPUS_IDS")
            continue

        print(f"\n[{i+1}/{len(courses)}] Processing Course: {course_name} (ID: {course_id})")

        course_dirname = convert_name(course_name, is_filename=False)
        course_output_path = os.path.join(BASE_OUTPUT_DIR, course_dirname)
        course_files_base_dir = os.path.join(course_output_path, "files")
        os.makedirs(course_output_path, exist_ok=True)

        print(f"  - Course directory: '{os.path.relpath(course_output_path, BASE_OUTPUT_DIR)}'")

        main_course_page_res = sess.get(course_url)
        soup_main = BeautifulSoup(main_course_page_res.text, HTML_PARSER)
        html_converter.baseurl = course_url # Set base URL for relative link resolution

        tab_links = soup_main.select('ul.nav-tabs.format_onetopic-tabs li a')
        content_areas_to_process = [] # (title, soup_obj, base_url, section_slug, is_main_tab)

        if not tab_links:
            print("    - No tabs found. Processing main page content.")
            content_areas_to_process.append(("main", soup_main, course_url, "main", True))
        else:
            print(f"    - Found {len(tab_links)} sections/tabs.")
            is_first_tab = True
            for tab_link in tab_links:
                section_title = tab_link.get_text(strip=True)
                section_url = tab_link.get('href')
                if not section_url or section_url.startswith('#'): continue

                section_url = urljoin(course_url, section_url)
                print(f"      - Fetching section: '{section_title}'")
                section_res = sess.get(section_url)
                soup_section = BeautifulSoup(section_res.text, HTML_PARSER)
                section_slug = convert_name(section_title, is_filename=False, default_name=f"section_{len(content_areas_to_process)}")
                content_areas_to_process.append((section_title, soup_section, section_url, section_slug, is_first_tab))
                is_first_tab = False

        processed_urls = set()
        for section_index, (title, soup, page_url, section_slug, is_main) in enumerate(content_areas_to_process):

            content_selector = 'ul.onetopic'
            content_elements = soup.select(content_selector) or [soup]

            print(f"      - Processing section: '{title}' (Files -> '{section_slug}')")
            section_files_dir = os.path.join(course_files_base_dir, section_slug)

            md_parts = []
            html_converter.baseurl = page_url
            for element in content_elements:
                is_fallback_soup = (len(content_elements) == 1 and element is soup)
                if not is_fallback_soup or element.select(content_selector):
                    if element.get_text(strip=True):
                         md_parts.append(html_converter.handle(str(element)))

            section_markdown = "\n\n---\n\n".join(md_parts) if md_parts else "*No significant text content found.*\n"

            md_filename = "main.md" if is_main else convert_name(section_slug, is_filename=True, default_name=f"section_{section_index}", extension=".md")
            md_file_title = f"{course_name} - {title}" + (" (Main)" if is_main else "")
            md_filepath = os.path.join(course_output_path, md_filename)
            full_markdown_content = f"# {md_file_title}\n\n{section_markdown}"
            save_markdown_content(md_filepath, full_markdown_content)

            links_to_check = []
            for element in content_elements:
                 links_to_check.extend(element.find_all('a', href=True))

            unique_links = {} # {absolute_url: link_element}
            for link in links_to_check:
                href = link.get('href')
                if not href or href.startswith(('#', 'javascript:')): continue

                absolute_url = urljoin(page_url, href)
                if absolute_url in processed_urls or absolute_url in unique_links: continue

                parsed_url = urlparse(absolute_url)
                is_moodle_resource_link = any(p in absolute_url for p in MOODLE_RESOURCE_PATHS)
                is_forced_download = 'forcedownload=1' in parsed_url.query

                if is_moodle_resource_link or is_forced_download:
                    unique_links[absolute_url] = link

            print(f"        - Found {len(unique_links)} unique potential files/folders.")
            for download_url, link in unique_links.items():
                 if download_url in processed_urls: continue

                 # Check if the link is a folder and handle it accordingly
                 if '/mod/folder/view.php' in download_url:
                     folder_name = link.get_text(strip=True) or f"folder_{len(processed_urls)}"
                     handle_folder_download(sess, download_url, section_files_dir, folder_name, processed_urls)
                     processed_urls.add(download_url)
                 else:
                     # Original file download logic
                     link_text = link.get_text(strip=True)
                     parsed_url = urlparse(download_url)
                     filename_from_path = os.path.basename(parsed_url.path)
                     _, ext_from_path = os.path.splitext(filename_from_path)

                     if filename_from_path and filename_from_path != 'view.php' and '.' in filename_from_path:
                          final_filename = sanitize_filename(filename_from_path)
                     elif link_text:
                          base_name = sanitize_filename(link_text, default_name=f"file_{len(processed_urls)}")
                          if '.' not in os.path.splitext(base_name)[1]:
                               guessed_ext = ext_from_path or mimetypes.guess_extension(link.get('type', '')) or '.file'
                               final_filename = base_name + guessed_ext
                          else:
                               final_filename = base_name
                     else:
                          final_filename = f"download_{len(processed_urls)}" + (ext_from_path or '.file')

                     download_file(sess, download_url, section_files_dir, final_filename)
                     processed_urls.add(download_url)

    print("\n--- Finished successfully ---")
