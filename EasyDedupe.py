# Wensheng Wang @2013
# WTFPL

# run pep8 with:
#   "flake8 --ignore=E501 EasyDedupe.py" or
#   "flake8 --max-line-length=100 EasyDedupepy"

import wx
import os
import hashlib
import threading

# Button definitions
ID_START = wx.NewId()
ID_STOP = wx.NewId()

# Define notification event for thread completion
EVT_RESULT_ID = wx.NewId()

TwoFolderInstruction = """Instruction:
Select the first and second folders, then click "Delete duplicates!!".
No files in the first folder will be deleted.
The files in the second folder that are duplicates of the ones in the first folder will be deleted.
Any empty folders in the second folder will also be deleted.
"""

OneFolderInstruction = """Instruction:
Select a folder, then click "Delete Duplicates!!".
The redundant files in this folder will be deleted.
Any empty folders in this folder will also be deleted.
"""


def EVT_RESULT(win, func):
    """Define Result Event."""
    win.Connect(-1, -1, EVT_RESULT_ID, func)


class ResultEvent(wx.PyEvent):
    """Simple event to carry arbitrary result data."""
    def __init__(self, data):
        """Init Result Event."""
        wx.PyEvent.__init__(self)
        self.SetEventType(EVT_RESULT_ID)
        self.data = data


def get_fhash(filename):
    key = hashlib.sha1()
    with open(filename, mode='rb') as f:
        key.update(f.read(1048576))
    return key.hexdigest()


class WorkerThread(threading.Thread):
    """Worker Thread Class."""
    def __init__(self, notify_window):
        """Init Worker Thread Class."""
        threading.Thread.__init__(self)
        self._notify_window = notify_window
        self._want_abort = 0
        # This starts the thread running on creation, but you could
        # also make the GUI thread responsible for calling this
        self.firstFiles = {}
        self.secondFiles = {}
        self.start()

    def run(self):
        """Run Worker Thread."""
        # This is the code executing in the new thread. Simulation of
        # a long process (well, 10s here) as a simple loop - you will
        # need to structure your processing so that you periodically
        # peek at the abort variable
        self.logFile = open("log.txt", 'w')
        number_of_files = 0
        if not self._notify_window.oneFolderOp:
            for root, dirs, files in os.walk(self._notify_window.firstFolder):
                for f in files:
                    fsize = os.path.getsize(os.path.join(root, f))
                    if fsize:
                        if fsize in self.firstFiles:
                            self.firstFiles[fsize].append((root, f))
                        else:
                            self.firstFiles[fsize] = [(root, f)]

                    if number_of_files % 200 == 0:
                        if self._want_abort:
                            # Use a result of None to acknowledge the abort (of
                            # course you can use whatever you'd like or even
                            # a separate event type)
                            wx.PostEvent(self._notify_window, ResultEvent(None))
                            return
                        wx.PostEvent(self._notify_window,
                                     ResultEvent({'n': number_of_files,
                                                  'l': os.path.join(root, f),
                                                  's': 0})
                                     )
                    number_of_files += 1

        number_of_files = 0
        number_of_deleted = 0
        for root, dirs, files in os.walk(self._notify_window.secondFolder, topdown=False):
            for f in files:
                fpath = os.path.join(root, f)
                fsize = os.path.getsize(fpath)
                if fsize == 0:
                    continue
                fhash = None

                # if oneFolderOp, we are building firstFiles here and checking against it
                # if not oneFolderOP, firstFiles already available
                if fsize in self.firstFiles:
                    for sf in self.firstFiles[fsize]:
                        # if filename is the same, there's no need to check hash
                        # TODO: even if filename and size are the same,
                        #       it can still be different images or zipfiles with padding
                        f2path = os.path.join(sf[0], sf[1])
                        if f == sf[1]:
                            # self.logFile.write("%s <is duplicate of> %s\n" %
                            #                    (fpath.encode('utf8'), f2path.encode('utf8')))
                            self.logFile.write("%s <is duplicate of> %s\n" % (fpath, f2path))
                            if self._notify_window.dryRun:
                                number_of_deleted += 1
                            else:
                                try:
                                    os.remove(fpath)
                                    number_of_deleted += 1
                                except OSError:
                                    # self.logFile.write("But can not delete %s\n" %
                                    #                    (fpath.encode('utf8')))
                                    self.logFile.write("But %s can not be deleted.\n" % fpath)
                            break
                        else:
                            # if sizes are the same, but filenames are different
                            # get hash of first 1M bytes
                            if not fhash:
                                fhash = get_fhash(fpath)
                            if fhash == get_fhash(f2path):
                                # self.logFile.write("!%s <is duplicate of> %s\n" %
                                #                    (fpath.encode('utf8'), f2path.encode('utf8')))
                                self.logFile.write("!%s <is duplicate of> %s\n" %
                                                   (fpath, f2path))
                                if self._notify_window.dryRun:
                                    number_of_deleted += 1
                                else:
                                    try:
                                        os.remove(fpath)
                                        number_of_deleted += 1
                                    except OSError:
                                        # self.logFile.write("But can not delete %s\n" %
                                        #                    (fpath.encode('utf8')))
                                        self.logFile.write("But %s can not be deleted.\n" % fpath)
                                break
                elif self._notify_window.oneFolderOp:
                    self.firstFiles[fsize] = [(root, f)]

                if number_of_files % 200 == 0:
                    if self._want_abort:
                        # Use a result of None to acknowledge the abort (of
                        # course you can use whatever you'd like or even
                        # a separate event type)
                        wx.PostEvent(self._notify_window, ResultEvent(None))
                        return
                    wx.PostEvent(self._notify_window,
                                 ResultEvent({'n': number_of_files,
                                              'l': os.path.join(root, f),
                                              's': 1})
                                 )
                number_of_files += 1

            # delete empty dirs
            if not self._notify_window.dryRun:
                for d in dirs:
                    dname = os.path.join(root, d)
                    try:
                        os.rmdir(dname)
                    except OSError:
                        pass

        # Here's where the result would be returned (this is an
        # example fixed result of the number 10, but it could be
        # any Python object)
        self.logFile.close()
        wx.PostEvent(self._notify_window, ResultEvent({'n': number_of_deleted, 's': 2}))

    def abort(self):
        """abort worker thread."""
        # Method for use by main thread to signal an abort
        self._want_abort = 1


class MyFrame(wx.Frame):
    def __init__(self, parent, id, title):
        wx.Frame.__init__(self, parent, id, title, size=(550, 420),
                          style=wx.DEFAULT_FRAME_STYLE ^ wx.RESIZE_BORDER)
        self.worker = None
        self.firstFolder = ""
        self.secondFolder = ""
        self.oneFolderOp = False
        self.dryRun = False

        self.deleted = 0  # 0:ready 1:in progress 2:done

        panel = wx.Panel(self, -1)
        title = wx.StaticText(panel, -1, "Easy Dedupe", pos=(170, 0))
        title.SetFont(wx.Font(24, wx.DECORATIVE, wx.ITALIC, wx.BOLD))

        self.chkbox = wx.CheckBox(panel, 0, 'Within one folder', pos=(220, 50))
        self.Bind(wx.EVT_CHECKBOX, self.OnChkbox, self.chkbox)

        self.firstButton = wx.Button(panel, 1, ' First Folder', size=(85, 28), pos=(5, 80))
        self.Bind(wx.EVT_BUTTON, self.OnFirst, id=1)
        self.txt1 = wx.TextCtrl(panel, size=(440, 30), pos=(95, 80), style=wx.TE_READONLY)

        self.secondButton = wx.Button(panel, 2, 'Second Folder', size=(85, 28), pos=(5, 110))
        self.Bind(wx.EVT_BUTTON, self.OnSecond, id=2)
        self.txt2 = wx.TextCtrl(panel, size=(440, 30), pos=(95, 110), style=wx.TE_READONLY)

        self.doButton = wx.Button(panel, 3, 'Delete Duplicates!!', (220, 170))
        self.Bind(wx.EVT_BUTTON, self.DoIt, id=3)
        self.txt3 = wx.TextCtrl(panel, size=(525, 120), pos=(10, 210),
                                style=wx.TE_READONLY | wx.TE_MULTILINE | wx.TE_WORDWRAP)
        self.txt3.SetValue(TwoFolderInstruction)

        self.dryrun = wx.CheckBox(panel,
                                  4,
                                  'Dry Run (No file will be deleted, \n'
                                  'check log.txt for what would be deleted if not dryrun)',
                                  pos=(100, 340))
        self.Bind(wx.EVT_CHECKBOX, self.OnDryRun, self.dryrun)

        # Set up event handler for any worker thread results
        EVT_RESULT(self, self.OnResult)

    def OnChkbox(self, event):
        if self.chkbox.Get3StateValue() == wx.CHK_CHECKED:
            self.firstButton.Hide()
            self.secondButton.SetLabel("Select Folder")
            self.txt1.Hide()
            self.txt3.SetValue(OneFolderInstruction)
            self.oneFolderOp = True
        else:
            self.firstButton.Show()
            self.secondButton.SetLabel("Second Folder")
            self.txt1.Show()
            self.txt3.SetValue(TwoFolderInstruction)
            self.oneFolderOp = False

    def OnDryRun(self, event):
        if self.dryrun.Get3StateValue() == wx.CHK_CHECKED:
            self.dryRun = True
        else:
            self.dryRun = False

    def OnResult(self, event):
        # event.data['s] 0:firstFiles 1:secondFiles 2:done
        if event.data is None:
            # Thread aborted (using our convention of None return)
            self.txt3.SetValue('Deleting task canceled.')
            self.doButton.SetLabel("Delete duplicates!!")
            self.worker = None
        elif event.data['s'] == 0:
            self.txt3.SetValue('In first folder: %d files scanned, lastfile is %s' %
                               (event.data['n'], event.data['l']))
        elif event.data['s'] == 1:
            self.txt3.SetValue('In second folder: %d files scanned, lastfile is %s' %
                               (event.data['n'], event.data['l']))
        else:
            # Process results here
            self.txt3.SetValue('Done! Total %d files were deleted.' % event.data['n'])
            self.worker = None
            self.doButton.SetLabel("Dupes Deleted!!")
            self.doButton.Disable()

    def ResetDoButton(self):
        self.doButton.Enable()
        self.doButton.SetLabel("Delete duplicates!!")
        self.deleted = 0

    def OnFirst(self, event):
        dlg = wx.DirDialog(self, "Select 1st folder")
        if dlg.ShowModal() == wx.ID_OK:
            self.firstFolder = dlg.GetPath()
            self.txt1.SetValue(self.firstFolder)
            self.ResetDoButton()
        dlg.Destroy()

    def OnSecond(self, event):
        dlg = wx.DirDialog(self, "Select 2nd folder")
        if dlg.ShowModal() == wx.ID_OK:
            self.secondFolder = dlg.GetPath()
            self.txt2.SetValue(self.secondFolder)
            self.ResetDoButton()
        dlg.Destroy()

    def DoIt(self, event):
        if self.deleted == 0:
            if self.oneFolderOp:
                if self.secondFolder == "":
                    self.txt3.SetValue("folders can not be empty")
                    return
            else:
                if (self.firstFolder == "" or self.secondFolder == "" or
                        self.firstFolder in self.secondFolder or
                        self.secondFolder in self.firstFolder):
                    self.txt3.SetValue("folders can not be empty or the same, "
                                       "one folder can NOT be subfolder of the other")
                    return

            self.deleted = 1
            self.doButton.SetLabel("Cancel deleting!")
            self.worker = WorkerThread(self)
        elif self.deleted == 1:
            self.txt3.SetValue("Canceling ...")
            self.deleted = 0
            self.worker.abort()


class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, -1, 'Easy Dedupe')
        frame.Show(True)
        frame.Centre()
        return True


if __name__ == "__main__":
    app = MyApp(0)
    app.MainLoop()
