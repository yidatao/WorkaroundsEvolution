from collections import namedtuple
import sys
import ProjectAttr
import os
import subprocess

#read workaround candidates
def read_workarounds(project):
    workarounds = []
    file = open('/d/workarounds/results/' + project.name + '-candidate','r')
    for line in file.readlines():
        commit_hash = line[:line.find(',')]
        in_msg = line[line.find('[')+1:line.find(']')]
        in_diff = line[line.rfind('[')+1:line.rfind(']')]

        msgKW = []
        diffKW = []
        for i in in_msg.split(','):
            i = i.strip()
            if i == '':
                continue
            msgKW.append(i[1:len(i)-1])
        for i in in_diff.split(','):
            i = i.strip()
            if i == '':
                continue
            diffKW.append(i[1:len(i)-1])

        commit = namedtuple('Commit', 'hash msgKW diffKW')
        workarounds.append(commit(commit_hash, msgKW, diffKW))
    return workarounds

#how workaround part evolves
def get_wr_child_candidate(workarounds):
    #<(wr_commit, wr_file):children>
    wr_children = {}

    for wr in workarounds:
        commit_hash = wr.hash
        msgKW = wr.msgKW
        diffKW = wr.diffKW

        #TODO test
        # if not commit_hash == '2bb6d5de002052680d443065e1c26f59be212e4b':
        #    continue

        #if the commit log mentions workaround keywords, we should check all the changed files
        all_file = False
        if len(msgKW) > 0:
            all_file = True

        cmd_file = 'git diff-tree --no-commit-id --name-only -r ' + commit_hash
        files = subprocess.check_output(cmd_file,shell=True)
        for file in files.decode().split('\n'):
            #test
            # if not file == 'src/org/junit/internal/runners/model/TestMethod.java':
            #    continue

            #filter non-workaround or non-interesting files
            if len(file)==0 or file.endswith('/changes.xml'):
                continue
            if not all_file and not is_workaround_file(commit_hash, file, diffKW):
                continue

            print(commit_hash + ',' + file)

            children = get_child_commit(commit_hash, file)
            wr_lines = []
            if all_file:
                #TODO not sure we should include oldline
                #context = 1 to increase recall (yet the precision might be low)
                wr_lines = get_all_change_lines(commit_hash, file, 1).newline
            else:
                wr_lines = get_wr_lines(commit_hash, file, diffKW, 1)

            #the interested lines in the previous commit
            real_child = []
            line_cursor = wr_lines
            for c in children:
                child_diff = get_all_change_lines(c, file, 0)
                #test
                # print(c + ': ' + str(child_diff))
                # print(line_cursor)

                if is_overlap(child_diff, line_cursor):
                    # print('overlap')
                    real_child.append(c)
                #update the cursor
                line_cursor = update_line_cursor(line_cursor, child_diff)

            if len(real_child) > 0:
                print(real_child)
                wr_children[(commit_hash, file)] = real_child

    write_result(project, wr_children)

#target is the interested part (i.e., workaround). After diff, get its current line range
def update_line_cursor(target, diff):
    new_target = []
    for t in target:
        startline = t[0]
        line_change = 0
        for l in diff.oldline:
            if len(l)>0 and l[0] <= startline:
                line_change = line_change - (l[1] - l[0] + 1)
        for l in diff.newline:
            if len(l)>0 and l[0] <= startline:
                line_change = line_change + (l[1] - l[0] + 1)
        new_target.append((t[0]+line_change, t[1]+line_change))
    return new_target

#get all the changed lines, apply to workaround commits whose keyword appear in the change log
def get_all_change_lines(commit_hash, file, context):
    #list of range tuple (startline, endline)
    old_line_range = []
    new_line_range = []

    cmd = 'git show -w --unified=' + str(context) + ' --pretty=format:b% ' + commit_hash + ' -- ' + file
    output = subprocess.check_output(cmd, shell=True)
    diff = []
    try:
        diff = output.decode().split('\n')
    except:
        pass
    for line in diff:
        if line.startswith('@@ '):
            lines = get_line_number(line)
            if len(lines.oldline) > 0 and not lines.oldline in old_line_range:
                old_line_range.append(lines.oldline)
            if len(lines.newline) > 0 and not lines.newline in new_line_range:
                new_line_range.append(lines.newline)

    result = namedtuple('result', 'oldline newline')
    return result(old_line_range,new_line_range)

#get the line range for workaround changes
#TODO: if many consecutive lines are changed, the line range might be very large, thus inaccurate for the exact location of workaround
def get_wr_lines(commit_hash, file, diffKW, context_count):
    #list of range tuple (startline, endline)
    line_ranges = []

    for kw in diffKW:
        #count the occurrence of the workaround keyword
        cmd_count = 'git show -w --unified=' + str(context_count) + ' --pretty=format:b% ' + commit_hash + ' -- ' + file + ' | grep -o -i \'' + kw + '\' | wc -l'
        count = subprocess.check_output(cmd_count, shell=True).decode()

        #obtain the line range for the ith occurrence
        for i in range(1, int(count)+1):
            # obtain the diff context before the ith occurrence
            cmd = 'git show -w --unified=' + str(context_count) + ' --pretty=format:b% ' + commit_hash + ' -- ' + file + ' | awk -v N='+ str(i) + ' -v M=\'' + kw + '\' \'BEGIN{IGNORECASE=1}{print}(N-=gsub(M,""))<=0{exit}\''
            output = subprocess.check_output(cmd, shell=True)

            context = output.decode().split('\n')
            #reverse to get the line range
            context.reverse()
            for line in context:
                if line.startswith('@@ '):
                    newline = get_line_number(line).newline
                    if len(newline) > 0 and not newline in line_ranges:
                        line_ranges.append(newline)
                    #only the nearest line range
                    break
    return line_ranges


#given a line starts with @@, get its diff line numbers
def get_line_number(line):
        rawline = ''
        if line.find(' @@ ') > -1:
            rawline = line[3:line.find(' @@ ')]
        else:
            rawline = line[3:line.find(' @@')]
        half1 = rawline[1:rawline.find(' +')]
        half2 = rawline[rawline.find(' +')+2:]


        #tuple (start-line, end-line)
        oldline = ()
        if ',' in half1:
            count = int(half1[half1.find(',')+1:])
            if not count == 0:
                startline = int(half1[:half1.find(',')])
                oldline = (startline, startline + count -1)
        else:
            oldline = (int(half1), int(half1))

        newline = ()
        if ',' in half2:
            count = int(half2[half2.find(',')+1:])
            if not count == 0:
                startline = int(half2[:half2.find(',')])
                newline = (startline,startline + count -1)
        else:
            newline = (int(half2), int(half2))

        result = namedtuple("result", "oldline newline")
        return result(oldline, newline)

def co_commit(commit_hash):
    cmd_co = 'git checkout ' + commit_hash
    print('checkout ' + commit_hash)

    retcode = subprocess.call(cmd_co,shell=True)
    if retcode != 0:
        print("check out failed " + commit_hash)
        sys.exit(0)

    cmd_hash = 'git rev-parse --short HEAD'
    output = subprocess.check_output(cmd_hash, shell=True)
    if not commit_hash.endswith('^') and not commit_hash.startswith(output.decode().strip()):
        print("check out inconsistent: " + commit_hash + ' vs. ' + output.decode())
        sys.exit(0)

#if the line range intersects
def is_overlap(child_diff, line_cursor):
    for l in child_diff.oldline:
        for lc in line_cursor:
            if not (l[1] < lc[0] or l[0] > lc[1]):
                return True
    for l in child_diff.newline:
        for lc in line_cursor:
            if not (l[1] < lc[0] or l[0] > lc[1]):
                return True
    return False

#get all the commits after the workaround commit, in chronological order
def get_child_commit(commit_hash, file):
    children = []
    cmd = 'git log --pretty=format:%h ' + commit_hash + '.. --reverse -- ' + file
    output = subprocess.check_output(cmd, shell=True)
    for l in output.decode().split('\n'):
        if len(l) > 0:
            children.append(l)
    return children

#if the file contains workaround
def is_workaround_file(commit_hash, file, diffKW):
    cmd = 'git show ' + commit_hash + ' -w --unified=0 --pretty=format:b% -- ' + file
    file_diff = subprocess.check_output(cmd, shell=True)

    for kw in diffKW:
        if kw in file_diff.decode().lower():
            return True
    return False

def write_result(project, result):
    content = ''
    for k,v in result.items():
        content = content + k[0] + ',' + k[1] + ',' + str(v) + '\n'

    file = open("/d/workarounds/results/" + project.name + '-evolve', "w")
    file.write(content)
    file.close()

if __name__ == "__main__":
    args = sys.argv
    projectName = args[1]
    project = ProjectAttr.getProjectAttr(projectName)
    os.chdir(project.repo)

    #set to HEAD
    cmd_hash = 'git rev-parse HEAD'
    output = subprocess.check_output(cmd_hash, shell=True)
    if not output.decode().strip() == project.head:
        print('reset HEAD')
        co_commit(project.head)

    workarounds = read_workarounds(project)
    get_wr_child_candidate(workarounds)
