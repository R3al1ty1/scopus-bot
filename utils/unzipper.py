import os
import zipfile


async def unzip_pngs(folder_path):
    for file_name in os.listdir(folder_path):
        file_path = os.path.join(folder_path, file_name)

        if zipfile.is_zipfile(file_path):
            archive_name = os.path.splitext(file_name)[0]
            new_base_name = archive_name.split(" ")[-1]
            
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                for file in zip_ref.infolist():
                    if file.filename.endswith(".png"):
                        extracted_path = zip_ref.extract(file, folder_path)
                        new_file_name = f"{new_base_name}.png"
                        if new_file_name[0] == "-":
                            new_file_name = new_file_name[1:]

                        new_file_path = os.path.join(folder_path, new_file_name)
                        counter = 1
                        while os.path.exists(new_file_path):
                            new_file_name = f"{new_base_name}_{counter}.png"
                            new_file_path = os.path.join(folder_path, new_file_name)
                            counter += 1

                        os.rename(extracted_path, new_file_path)

            os.remove(file_path)
    return True