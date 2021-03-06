import json
import urllib
import flask
import random

#from flaskext.login import login_user, logout_user, current_user

from base import web, model, Fixtures, db
from pybossa import sched

from nose.tools import assert_equal


class TestSCHED:
    def setUp(self):
        self.app = web.app.test_client()
        model.rebuild_db()
        Fixtures.create()
        self.endpoints = ['app', 'task', 'taskrun']

    def tearDown(self):
        db.session.remove()

    @classmethod
    def teardown_class(cls):
        model.rebuild_db()

    def isTask(self, task_id, tasks):
        """Returns True if the task_id is in tasks list"""
        for t in tasks:
            if t.id==task_id:
                return True
        return False

    def isUnique(self,id,items):
        """Returns True if the id is not Unique"""
        copies = 0
        for i in items:
            if type(i) is dict:
                if i['id'] == id:
                    copies = copies + 1
            else:
                if i.id == id:
                    copies = copies + 1
        if copies>=2:
            return False
        else:
            return True

    def delTaskRuns(self, app_id=1):
        """Deletes all TaskRuns for a given app_id"""
        db.session.query(model.TaskRun).filter_by(app_id=1).delete()
        db.session.commit()
        db.session.remove()

    def register(self, method="POST", fullname="John Doe", username="johndoe", password="p4ssw0rd", password2=None, email=None):
        """Helper function to register and sign in a user"""
        if password2 is None:
            password2 = password
        if email is None:
            email = username + '@example.com'
        if method == "POST":
            return self.app.post('/account/register', data = {
                'fullname': fullname,
                'username': username,
                'email_addr': email,
                'password': password,
                'confirm': password2,
                }, follow_redirects = True)
        else:
            return self.app.get('/account/register', follow_redirects = True)

    def signin(self, method="POST", username="johndoe", password="p4ssw0rd", next=None):
        """Helper function to sign in current user"""
        url = '/account/signin'
        if next != None:
            url = url + '?next=' + next
        if method == "POST":
            return self.app.post(url, data =  {
                    'username': username,
                    'password': password,
                    }, follow_redirects = True)
        else:
            return self.app.get(url, follow_redirects = True)

    def signout(self):
        """Helper function to sign out current user"""
        return self.app.get('/account/signout', follow_redirects = True)


    def test_anonymous_01_newtask(self):
        """ Test SCHED newtask returns a Task for the Anonymous User"""
        # Del previous TaskRuns
        self.delTaskRuns()

        res = self.app.get('api/app/1/newtask')
        data = json.loads(res.data)
        assert data['info'], data


    def test_anonymous_02_gets_different_tasks(self):
        """ Test SCHED newtask returns N different Tasks for the Anonymous User"""
        # Del previous TaskRuns
        self.delTaskRuns()


        assigned_tasks = []
        # Get a Task until scheduler returns None
        res = self.app.get('api/app/1/newtask')
        data = json.loads(res.data)
        while (data.get('info')!=None):
            # Check that we have received a Task
            assert data.get('info'),  data

            # Save the assigned task
            assigned_tasks.append(data)

            # Submit an Answer for the assigned task
            tr = model.TaskRun(app_id=data['app_id'], task_id=data['id'], 
                               user_ip="127.0.0.1",
                               info={'answer': 'Yes'})
            db.session.add(tr)
            db.session.commit()
            res = self.app.get('api/app/1/newtask')
            data = json.loads(res.data)

        # Check if we received the same number of tasks that the available ones
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        assert len(assigned_tasks) == len(tasks), len(assigned_tasks)
        # Check if all the assigned Task.id are equal to the available ones
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        for at in assigned_tasks:
            assert self.isTask(at['id'],tasks), "Assigned Task not found in DB Tasks"
        # Check that there are no duplicated tasks
        for at in assigned_tasks:
            assert self.isUnique(at['id'],assigned_tasks), "One Assigned Task is duplicated"

    def test_anonymous_03_respects_limit_tasks(self):
        """ Test SCHED newtask respects the limit of 30 TaskRuns per Task"""
        # Del previous TaskRuns
        self.delTaskRuns()

        assigned_tasks = []
        # Get Task until scheduler returns None
        for i in range(10):
            res = self.app.get('api/app/1/newtask')
            data = json.loads(res.data)

            while (data.get('info')!=None):
                # Check that we received a Task
                assert data.get('info'),  data

                # Save the assigned task
                assigned_tasks.append(data)

                # Submit an Answer for the assigned task
                tr = model.TaskRun(app_id=data['app_id'], task_id=data['id'], 
                                   user_ip="127.0.0." + str(i),
                                   info={'answer': 'Yes'})
                db.session.add(tr)
                db.session.commit()
                res = self.app.get('api/app/1/newtask')
                data = json.loads(res.data)

        # Check if there are 30 TaskRuns per Task
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        for t in tasks:
            assert len(t.task_runs)==10, len(t.task_runs)
        # Check that all the answers are from different IPs
        for t in tasks:
            for tr in t.task_runs:
                assert self.isUnique(tr.user_ip,t.task_runs), "There are two or more Answers from same IP"


    def test_user_01_newtask(self):
        """ Test SCHED newtask returns a Task for John Doe User"""
        # Del previous TaskRuns
        self.delTaskRuns()

        # Register
        self.register()
        self.signin()
        res = self.app.get('api/app/1/newtask')
        data = json.loads(res.data)
        assert data['info'], data
        self.signout()


    def test_user_02_gets_different_tasks(self):
        """ Test SCHED newtask returns N different Tasks for John Doe User"""
        # Del previous TaskRuns
        self.delTaskRuns()

        # Register
        self.register()
        self.signin()

        assigned_tasks = []
        # Get Task until scheduler returns None
        res = self.app.get('api/app/1/newtask')
        data = json.loads(res.data)
        while (data.get('info')!=None):
            # Check that we received a Task
            assert data.get('info'),  data

            # Save the assigned task
            assigned_tasks.append(data)

            # Submit an Answer for the assigned task
            tr = dict(
                    app_id = data['app_id'],
                    task_id = data['id'],
                    info = {'answer': 'No'}
                    )
            tr = json.dumps(tr)

            self.app.post('/api/taskrun', data=tr)
            res = self.app.get('api/app/1/newtask')
            data = json.loads(res.data)

        # Check if we received the same number of tasks that the available ones
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        assert len(assigned_tasks) == len(tasks), assigned_tasks
        # Check if all the assigned Task.id are equal to the available ones
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        for at in assigned_tasks:
            assert self.isTask(at['id'],tasks), "Assigned Task not found in DB Tasks"
        # Check that there are no duplicated tasks
        for at in assigned_tasks:
            assert self.isUnique(at['id'],assigned_tasks), "One Assigned Task is duplicated"

    def test_user_03_respects_limit_tasks(self):
        """ Test SCHED newtask respects the limit of 30 TaskRuns per Task"""
        # Del previous TaskRuns
        self.delTaskRuns()

        assigned_tasks = []
        # We need one extra loop to allow the scheduler to mark a task as completed
        for i in range(11):
            self.register(fullname="johndoe"+str(i),username="johndoe"+str(i),password="johndoe"+str(i))
            print "Number of users %s" % len(db.session.query(model.User).all())
            print "Giving answers as User: %s" % "johndoe"+str(i)
            self.signin()
            # Get Task until scheduler returns None
            res = self.app.get('api/app/1/newtask')
            data = json.loads(res.data)

            while (data.get('info')!=None):
                # Check that we received a Task
                assert data.get('info'),  data

                # Save the assigned task
                assigned_tasks.append(data)

                # Submit an Answer for the assigned task
                tr = dict(
                        app_id = data['app_id'],
                        task_id = data['id'],
                        info = {'answer': 'No'}
                        )
                tr = json.dumps(tr)
                self.app.post('/api/taskrun', data=tr)

                res = self.app.get('api/app/1/newtask')
                data = json.loads(res.data)
            self.signout()

        # Check if there are 30 TaskRuns per Task
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        for t in tasks:
            print len(t.task_runs)
            assert len(t.task_runs)==10, t.task_runs
        # Check that all the answers are from different IPs
        for t in tasks:
            for tr in t.task_runs:
                assert self.isUnique(tr.user_id,t.task_runs), "There are two or more Answers from same User"
        # Check that task.state is updated to completed
        for t in tasks:
            assert t.state=="completed", t.state

    def test_tasks_for_user_ip_id(self):
        """ Test SCHED newtask to see if sends the same ammount of Task to 
            user_id and user_ip
        """
        # Del Fixture Task
        self.delTaskRuns()

        assigned_tasks = []
        for i in range(10):
            signin = False
            if random.random >= 0.5:
                signin = True
                self.register(fullname="johndoe"+str(i),username="johndoe"+str(i),password="johndoe"+str(i))

            if signin:
                print "Giving answers as User: %s" % "johndoe"+str(i)
            else:
                print "Giving answers as User IP: 127.0.0.%s" % str(i)

            if signin:
                self.signin()
            # Get Task until scheduler returns None
            res = self.app.get('api/app/1/newtask')
            data = json.loads(res.data)

            while (data.get('info')!=None):
                # Check that we received a Task
                assert data.get('info'),  data

                # Save the assigned task
                assigned_tasks.append(data)

                # Submit an Answer for the assigned task
                if signin:
                    tr = dict(
                            app_id = data['app_id'],
                            task_id = data['id'],
                            info = {'answer': 'No'}
                            )
                    tr = json.dumps(tr)
                    self.app.post('/api/taskrun', data=tr)
                else:
                    tr = model.TaskRun(app_id=data['app_id'], task_id=data['id'], 
                                       user_ip="127.0.0." + str(i),
                                       info={'answer': 'Yes'})
                    db.session.add(tr)
                    db.session.commit()

                res = self.app.get('api/app/1/newtask')
                data = json.loads(res.data)
            if signin:
                self.signout()

        # Check if there are 30 TaskRuns per Task
        tasks = db.session.query(model.Task).filter_by(app_id=1).all()
        for t in tasks:
            print len(t.task_runs)
            assert len(t.task_runs)==10, t.task_runs
        # Check that all the answers are from different IPs and IDs
        for t in tasks:
            for tr in t.task_runs:
                if tr.user_id:
                    assert self.isUnique(tr.user_id,t.task_runs), "There are two or more Answers from same User ID"
                else:
                    assert self.isUnique(tr.user_ip,t.task_runs), "There are two or more Answers from same User IP"

    def test_task_preloading(self):
        """Test TASK Pre-loading works"""
        # Del previous TaskRuns
        self.delTaskRuns()

        # Register
        self.register()
        self.signin()

        assigned_tasks = []
        # Get Task until scheduler returns None
        res = self.app.get('api/app/1/newtask')
        task1 = json.loads(res.data)
        # Check that we received a Task
        assert task1.get('info'),  task1
        # Pre-load the next task for the user
        res = self.app.get('api/app/1/newtask?offset=1')
        task2 = json.loads(res.data)
        # Check that we received a Task
        assert task2.get('info'),  task2
        # Check that both tasks are different
        assert task1.get('id') != task2.get('id'), "Tasks should be different"
        ## Save the assigned task
        assigned_tasks.append(task1)
        assigned_tasks.append(task2)

        # Submit an Answer for the assigned and pre-loaded task
        for t in assigned_tasks:
            tr = dict(
                    app_id=t['app_id'],
                    task_id=t['id'],
                    info={'answer': 'No'}
                    )
            tr = json.dumps(tr)

            self.app.post('/api/taskrun', data=tr)
        # Get two tasks again
        res = self.app.get('api/app/1/newtask')
        task3 = json.loads(res.data)
        # Check that we received a Task
        assert task3.get('info'),  task1
        # Pre-load the next task for the user
        res = self.app.get('api/app/1/newtask?offset=1')
        task4 = json.loads(res.data)
        # Check that we received a Task
        assert task4.get('info'),  task2
        # Check that both tasks are different
        assert task3.get('id') != task4.get('id'), "Tasks should be different"
        assert task1.get('id') != task3.get('id'), "Tasks should be different"
        assert task2.get('id') != task4.get('id'), "Tasks should be different"
        # Check that a big offset returns None
        res = self.app.get('api/app/1/newtask?offset=11')
        print json.loads(res.data)
        assert json.loads(res.data)=={}, res.data


class TestGetBreadthFirst:
    @classmethod
    def teardown_class(cls):
        model.rebuild_db()

    def tearDown(self):
        db.session.remove()

    def delTaskRuns(self, app_id=1):
        """Deletes all TaskRuns for a given app_id"""
        db.session.query(model.TaskRun).filter_by(app_id=1).delete()
        db.session.commit()
        db.session.remove()

    def test_get_default_task_anonymous(self):
        self._test_get_breadth_first_task()

    def test_get_breadth_first_task_user(self):
        user = Fixtures.create_users()[0]
        self._test_get_breadth_first_task(user)

    def _test_get_breadth_first_task(self, user=None):
        self.delTaskRuns()
        if user:
            short_name = 'xyzuser'
        else:
            short_name = 'xyznouser'
        app = model.App(short_name=short_name)
        task = model.Task(app=app, state = '0', info={})
        task2 = model.Task(app=app, state = '0', info={})
        db.session.add(app)
        db.session.add(task)
        db.session.add(task2)
        db.session.commit()
        taskid = task.id
        appid = app.id
        # give task2 a bunch of runs
        for idx in range(2):
            self._add_task_run(task2)

        # now check we get task without task runs
        out = sched.get_breadth_first_task(appid)
        assert out.id == taskid, out

        # now check that offset works
        out1 = sched.get_breadth_first_task(appid)
        out2 = sched.get_breadth_first_task(appid,offset=1)
        assert out1.id != out2.id, out

        # asking for a bigger offset (max 10)
        out2 = sched.get_breadth_first_task(appid,offset=11)
        assert out2 is None, out

        self._add_task_run(task)
        out = sched.get_breadth_first_task(appid)
        assert out.id == taskid, out

        # now add 2 more taskruns. We now have 3 and 2 task runs per task
        self._add_task_run(task)
        self._add_task_run(task)
        out = sched.get_breadth_first_task(appid)
        assert out.id == task2.id, out

    def _add_task_run(self, task, user=None):
        tr = model.TaskRun(task=task, user=user)
        db.session.add(tr)
        db.session.commit()
