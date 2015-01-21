import os
import subprocess
import sys
import ProjectAttr
from collections import namedtuple

fix_keywords = [' fix', ' bug', ' error', ' issue', ' defect', ' patch']

def detect_fix_commit(project):
    head_commit = subprocess.check_output('git rev-parse HEAD', shell=True)
    if head_commit.decode().strip() != project.head:
        co_commit(project.head)

    fix_commits = []

    cmd_log = 'git log --pretty=format:%H,%s'
    PIPE = subprocess.PIPE
    p = subprocess.Popen(cmd_log,shell=True,stdout=PIPE,stderr=PIPE)
    (sOut,sErr) = (p.stdout,p.stderr)

    for commit in sOut.readlines():
        commit = commit.decode()
        commit_hash = commit[:commit.find(',')]
        commit_msg = commit[commit.find(',')+1:]

        for k in fix_keywords:
            if k in commit_msg.lower():
                if not commit_hash in fix_commits:
                    fix_commits.append(commit_hash)

    print('# of fix commits: ' + str(len(fix_commits)))
    return fix_commits

def trace_inducing_commit(project, fix_commit):
    culprit = []
    result = diff_line_range(fix_commit)

    print(fix_commit + ' :')

    #new lines
    co_commit(fix_commit)
    for file, lines in result.newline.items():
        # l is a tuple
        for l in lines:
            startline = int(l[1])
            count = int(l[2])
            # nothing changed, continue
            if count == 0:
                continue
            endline = startline + count - 1
            #not sure on the fix_commit
            cmd = 'git log -w -L ' + str(startline) + ',' + str(endline) + ':' + file
            output = subprocess.check_output(cmd, shell=True)

            output_decode = ''
            try:
                output_decode = output.decode()
            except:
                pass
            for o in output_decode.split('\n'):
                if o.startswith("commit "):
                    commit_hash = o[7:]
                    if not commit_hash in culprit:
                        culprit.append(commit_hash)
    #old lines (checkout the parent commit)
    co_commit(fix_commit + '^')
    for file, lines in result.oldline.items():
        # l is a tuple
        for l in lines:
            startline = int(l[1])
            count = int(l[2])
            # nothing changed, continue
            if count == 0:
                continue
            endline = startline + count - 1
            #not sure on the fix_commit
            #alternatively, we can start from the workaround commit, and see how it evolves to the HEAD
            #e.g., git log 4c7101b4a306e15aa51618b283bd870b0387f263..HEAD --reverse -L180,181:src/org/apache/xml/serialize/HTMLSerializer.java
            #this way, we can save time by not backward tracing all the fix commits
            #issue: since we checkout, the current HEAD is the commit. If we don't checkout, the line number is not correct since it points to the head
            #one way is we log the history of the file instead of lines, then check the lines
            cmd = 'git log -w -L ' + str(startline) + ',' + str(endline) + ':' + file
            output = subprocess.check_output(cmd, shell=True)

            output_decode = ''
            try:
                output_decode = output.decode()
            except:
                pass
            for o in output_decode.split('\n'):
                if o.startswith("commit "):
                    commit_hash = o[7:]
                    if not commit_hash in culprit:
                        culprit.append(commit_hash)

    write_result(project, fix_commit, culprit)
    print(str(len(culprit)) + ' inducing')
    return culprit

def trace_workaround_culprit(project, cursor):
    fix_commits = detect_fix_commit(project)
    culprit = set()
    skip = True
    for fc in fix_commits:
        #start from the cursor
        if not cursor is None:
            if cursor == fc:
                skip = False
            if skip:
                continue

        inducing = trace_inducing_commit(project, fc)
        culprit = culprit | set(inducing)

    culprit_workaround = []
    file = open('/d/workarounds/results/' + project.name + '-candidate','r')
    for line in file.readlines():
        wr_commit = line[:line.find(',')]
        if wr_commit in culprit:
            culprit_workaround.append(wr_commit)

    #back to the HEAD
    co_commit(project.head)

    print('# of culprit workaround: ' + str(len(culprit_workaround)))
    print('# of total workaround: ' + str(sum(1 for line in open('/d/workarounds/results/' + project.name + '-candidate'))))

def diff_line_range(commit):
    #map a file to a list of tuples (startLine, range), which represent its diff
    old_map = {}
    new_map = {}
    #-w: ignore whitespace, --unified specifies 0 context lines (so that we can accurately get changed lines)
    #--diff-filter=M only include modified files TODO: may also consider deleted files
    cmd_diff = 'git diff -w --unified=0 --diff-filter=M ' + commit + '^ ' + commit
    commit_diff = subprocess.check_output(cmd_diff, shell = True)

    cur_file = ''
    cur_old_lines = [] # list of tuples (startline, count)
    cur_new_lines = []

    diff_decoded = ''
    try:
        diff_decoded = commit_diff.decode()
    except:
        pass

    for line in diff_decoded.split("\n"):
        if line.startswith('diff --git '):
            #store to the map
            if not cur_file == '':
                old_map[cur_file] = cur_old_lines
                new_map[cur_file] = cur_new_lines

            #re-initialize
            cur_file = line[13:line.rfind(' b/')]
            cur_old_lines = []
            cur_new_lines = []
        if line.startswith('@@ '):
            rawline = ''
            if line.find(' @@ ') > -1:
                rawline = line[3:line.find(' @@ ')]
            else:
                rawline = line[3:line.find(' @@')]
            half1 = rawline[1:rawline.find(' +')]
            half2 = rawline[rawline.find(' +')+2:]


            #tuple (old or new, start-line, count)
            oldline = ()
            if ',' in half1:
                count = half1[half1.find(',')+1:]
                if not count == '0':
                    oldline = ('o', half1[:half1.find(',')], count)
            else:
                oldline = ('o', half1, 1)
            newline = ()
            if ',' in half2:
                count = half2[half2.find(',')+1:]
                if not count == '0':
                    newline = ('n', half2[:half2.find(',')],count)
            else:
                newline = ('n',half2, 1)

            if len(oldline) > 0:
                cur_old_lines.append(oldline)
            if len(newline) > 0:
                cur_new_lines.append(newline)

    # the last file
    if not cur_file == '':
        old_map[cur_file] = cur_old_lines
        new_map[cur_file] = cur_new_lines

    Result = namedtuple('Result', 'oldline newline')
    return Result(old_map, new_map)

def print_file_line(map):
    for k,v in map.items():
        print(k + str(v))

def co_commit(commit_hash):
    cmd_co = 'git checkout ' + commit_hash
    print('checkout ' + commit_hash)

    retcode = subprocess.call(cmd_co,shell=True)
    if retcode != 0:
        print("check out failed " + commit_hash)
        sys.exit(0)

    cmd_hash = 'git rev-parse HEAD'
    output = subprocess.check_output(cmd_hash, shell=True)
    if not commit_hash.endswith('^') and not commit_hash == output.decode().strip():
        print("check out inconsistent: " + commit_hash + ' vs. ' + output.decode())
        sys.exit(0)

def write_result(project, fix_commit, culprit_commits):
    file = open("/d/workarounds/stats/" + project.name + '-culprit', "a")
    file.write(fix_commit + ',' + str(culprit_commits) + '\n')
    file.close()

#identify bug fix commits -> trace back
#slow because of large amount of bug fix commits
if __name__ == "__main__":
    args = sys.argv
    projectName = args[1]
    project = ProjectAttr.getProjectAttr(projectName)
    os.chdir(project.repo)
    #TODO the cursor seems not working right
    # cursor is the last fix_commit that has been processed
    cursor = None
    if len(args) == 3:
        cursor = args[2]

    #co_commit('127f1bb2a137d611e98277a0d1e9184efc47bc05')
    trace_workaround_culprit(project, cursor)
    #diff_line_range('0baf29c6e5669fd5c3e5f5cbc326d201ccdc5b3c')
    #trace_inducing_commit('0baf29c6e5669fd5c3e5f5cbc326d201ccdc5b3c')
    #trace_workaround_culprit(project)
    #fix_commits = detect_fix_commit(project)
    #print(len(fix_commits))
    #map = diff_line_range('22f68238a49995ff90d0a5b80069c5ce0a399d4d')
    #print(map)