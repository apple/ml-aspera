import os
import pkgutil

package_dir = os.path.dirname(__file__)

module_names = []
for module_info in pkgutil.iter_modules([package_dir]):
    module_names.append(module_info.name)
    __import__(f"{__name__}.{module_info.name}")
