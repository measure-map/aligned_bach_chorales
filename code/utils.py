import os


def get_dcml_files(path, extension='.tsv', remove_extension=True):
    """Corrects the error in the CPE numbering by turning the duplicate "283bis" into 284 and correcting all
    following 284, 285... by +1
    """
    number2file = {}
    for fname in os.listdir(path):
        if not fname.endswith(extension):
            continue
        number = int(fname[:3])
        l_ext = len(extension)
        title = fname[4:-l_ext]
        if number > 282:
            if number == 283:
                if fname[:6] == '283bis':
                    number += 1 
                    title = fname[7:-l_ext]
                else:
                    pass
            else:
                number += 1
        if remove_extension:
            fname = fname[:-l_ext]
        number2file[number] = (fname, title)
    result = {i: number2file.get(i) for i in range(1, 372)}
    return result