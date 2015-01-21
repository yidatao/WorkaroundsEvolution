import subprocess
import ProjectAttr
import sys
import os
from collections import namedtuple
#revisit?
workaround_keywords = [' workaround',' work around',' work-around',' temporary solution',' temporary fix',' hack',' quick fix']
no_workaround_keywords = ['hacker\'s delight']


#search commits that might be workarounds
def searchWorkaround_git(project, cursor):
    os.chdir(project.repo)
    cmd_log = 'git log --pretty=format:%H,%s'
    log = subprocess.check_output(cmd_log,shell=True)

    skip = True
    for commit in log.decode().split("\n"):
        commit_hash = commit[:commit.find(',')]
        commit_msg = commit[commit.find(',')+1:]

        #start from the cursor
        if not cursor is None:
            if cursor == commit_hash:
                skip = False
            if skip:
                continue

        cmd_file = 'git diff-tree --no-commit-id --name-only -r ' + commit_hash
        files = subprocess.check_output(cmd_file,shell=True)

        hasCodeChange = False
        for file in files.decode().split('\n'):
            if file.endswith('.java'):
                hasCodeChange = True
                break
        if not hasCodeChange:
            continue

        print(commit_hash)
        #-w: ignore whitespace
        #--unified=0: no context
        cmd_diff = 'git show -w --unified=0 --pretty=format:%b ' + commit_hash
        commit_diff = subprocess.check_output(cmd_diff, shell = True)

        res = containKeyword(commit_msg, commit_diff)

        if res.isContain:
            writeIDs(project, commit_hash, res.note)

    print('# workarounds: ' + str(sum(1 for line in open('/d/workarounds/results/' + project.name + '-candidate'))))
    print('# total: ' + str(len(log.decode().split("\n"))))

#whether commit log and diff contains the workaround keywords
def containKeyword(msg, diff):
    hasKeyword = False
    inMsg = []
    inDiff = []
    for keyword in workaround_keywords:
        #case insensitive
        if not msg is None and keyword in msg.lower():
            inMsg.append(keyword)
            hasKeyword = True

        diffStr = ''
        try:
            diffStr = diff.decode()
        except:
            pass
        if keyword in diffStr.lower():
            inDiff.append(keyword)
            hasKeyword = True
    result = namedtuple('Result', 'isContain note')
    return result(hasKeyword, str(inMsg) + ',' + str(inDiff))

def isSkip(project, commit):
    skip = False
    if project.name == 'Log4j2':
        if commit == '1419697':
            skip = True
    return skip

def writeIDs(project, revID, note):
    line = revID + ',' + note + '\n'
    file = open("/d/workarounds/results/" + project.name + '-candidate', "a")
    file.write(line)
    file.close()

if __name__ == "__main__":
    args = sys.argv
    projectName = args[1]
    # cursor in case the execution fails, then start from the failure point
    cursor = None
    if len(args) == 3:
        cursor = args[2]
    project = ProjectAttr.getProjectAttr(projectName)
    searchWorkaround_git(project, cursor)