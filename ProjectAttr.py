from collections import namedtuple
import os

def getProjectAttr(projectName):
    Project = namedtuple('Project','name repo type head url')

    git_path = os.path.abspath(os.path.join(os.getcwd(), "../git_repo"))
    repo = ''
    type = ''
    head = ''
    url = ''
    if projectName == 'log4j2':
        repo = git_path + '/log4j2'
        type = 'git'
        head = '5ad6d6f570fab5294334d972ed4b218efd92e6d5'
        url = 'git://git.apache.org/logging-log4j2.git'
    elif projectName == 'ant':
        repo = git_path + '/ant'
        type = 'git'
        head = '66c2551a594f3e5498c623ca1ad5285c4ccaf11c'
        url = 'git://git.apache.org/ant.git'
    elif projectName == 'xerces':
        repo = git_path + '/xerces'
        type = 'git'
        head = '219f15bf956c06e5939d5e6032188fac44270701'
        url = 'git://git.apache.org/xerces2-j.git'
    elif projectName == 'eclipseJDT':
        repo = git_path + '/eclipseJDT'
        type = 'git'
        head = '62542d77179e2d9d9eae2d205be3f0fefe8aabb4'
        url = 'git://git.eclipse.org/gitroot/jdt/eclipse.jdt.core.git'
    elif projectName == 'gwt':
        repo = git_path + '/gwt'
        type = 'git'
        head = '80098e66bd1d75890453524f2f6688709c85281a'
        url = 'https://gwt.googlesource.com/gwt'
    elif projectName == 'junit':
        repo = git_path + '/junit'
        type = 'git'
        head = '127f1bb2a137d611e98277a0d1e9184efc47bc05'
        url = 'https://github.com/junit-team/junit.git'
    elif projectName == 'guava':
        repo = git_path + '/guava'
        type = 'git'
        head = '0f91c0fe460a9a753d7040a5691c38cee31dad92'
        url = 'https://code.google.com/p/guava-libraries/'


    return Project(projectName, repo, type, head, url)