
class App {
   constructor() {
      this.workflows = {}
   }
   init() {
      // TODO: add pagination
      this.fetchWorkflows(0,50)
   }

   responseFilter(response) {
      if (response.status==401) {
         // Setup auth
         //setTimeout(() => { this.relogin(); },10);
         return null
      } else {
         return response.json()
      }
   }

   fetchWorkflows(start,size) {
      fetch(`service/workflows?next=${start}&size=${size}`)
         .then(response => this.responseFilter(response))
         .then(data => {
            this.addWorkflows(data);
         })
         .catch(error => {
            console.log(error)
         })
   }

   addWorkflows(data) {
      for (let workflow of data) {
         let exists = this.workflows[workflow.id] != null;
         this.workflows[workflow.id] = workflow
         if (exists) {
            // TODO: update UI
         } else {
            let item = $(`<li><a class="uk-accordion-title" href="#"><span class="uk-width-expand" uk-leader>${workflow.id}</span><span class='state'>${workflow.state}</span></a><div class="uk-accordion-content"><div uk-spinner></div></div></li>`).appendTo("#workflows");
            workflow.item = item;
            workflow.loaded = false;
            workflow.shown = false;
            workflow.states_shown = false
            $(item)
              .find("a")
              .click(() => {
                 this.showWorkflowDetails(workflow);
              });

         }
      }
   }

   showWorkflowDetails(workflow) {
      if (!workflow.loaded) {
         this.fetchWorkflowGraph(
            workflow,
            () => {
               this.fetchWorkflowDetails(
                  workflow,
                  () => {
                     this.fetchWorkflowTrace(
                        workflow,
                        () => {
                           workflow.loaded = true
                           this.showWorkflowDetails(workflow)
                        }
                     );
                  }
               )
            }
         )
         return;
      }
      if (workflow.shown) {
         return;
      }
      console.log(`Loaded ${workflow.id}`)
      setTimeout(() => {
         this.fetchWorkflowStatus(
            workflow,
            () => {
               $(workflow.item).find(".state").empty().text(workflow.state);
            }
         );
      },10)
      $(workflow.item).find(".uk-accordion-content").empty();
      let content = $(workflow.item).find(".uk-accordion-content");
      let nav_html = '<ul class="uk-iconnav">'
      let icons = [["info","show states"],["refresh","refresh workflow"],["copy","copy workflow state"]]
      if (workflow.state=='TERMINATED') {
         icons.push(["play","resume workflow"]);
         icons.push(["trash","delete workflow"]);
      } else if (workflow.state=='RUNNING') {
         icons.push(["ban","stop workflow"]);
      } else if (workflow.state=='FINISHED') {
         icons.push(["trash","delete workflow"]);
      }
      for (let [icon,title] of icons) {
         nav_html += `<li><a href="#${icon}" uk-icon="icon: ${icon}" title="${title}"></a></li>`
      }
      nav_html += "</ul>";
      let nav = $(nav_html).appendTo(content);

      $(`<div class="mermaid">${workflow.graph.mermaid}</div>`).appendTo(content);
      mermaid.init({}, $(workflow.item).find(".uk-accordion-content .mermaid"));
      workflow.shown = true;
      // TODO: need a callback from above
      let self = this;
      for (let link of $(nav).find('a')) {
         let href = $(link).attr('href');
         $(link).click(() => {
            console.log(`${workflow.id} ${href}`);
            if (href=='#refresh') {
               workflow.loaded = false;
               workflow.shown = false;
               this.showWorkflowDetails(workflow);
            } else if (href=='#info') {
               if (workflow.states_shown) {
                  let content = $(workflow.item).find(".uk-accordion-content");
                  $(content).find("table").remove();
                  workflow.states_shown = false
                  $(link).attr("title","show states")
               } else {
                  this.showWorkflowTaskDetails(workflow);
                  $(link).attr("title","hide states")
               }
            } else if (href=='#play') {
               UIkit.modal.alert('The resume functionality is not implemented.');
            } else if (href=='#copy') {
               UIkit.modal.alert('The copy functionality is not implemented.');
            } else if (href=='#ban') {
               UIkit.modal.confirm(`Are you sure you want to stop workflow ${workflow.id}`).then(() => {
                  this.terminateWorkflow(workflow);
               });
            } else if (href=='#trash') {
               UIkit.modal.confirm(`Are you sure you want to delete workflow ${workflow.id}`).then(() => {
                  this.deleteWorkflow(workflow);
               });
            }
         })
      }
      if (workflow.states_shown) {
         workflow.states_shown = false
         this.showWorkflowTaskDetails(workflow);
      }
      setTimeout(() => {
         for (let g of $(workflow.item).find('svg .statediagram-state')) {
            let id = g.getAttribute('id')
            let parts = id.split('-');

            // Note: This is a bug in mermaid
            if (parts[1]=='</join></fork>') {
              g.remove();
              continue;
            }
            let [name,index] = parts[1].split(".")
            let node =  {"element" : g, "id":id, "index": parseInt(index)}
            workflow.graph.tasks[name] = node
            $(g).hover(() => {
               this.showWorkflowNode(workflow,node)
            })
         }
         for (let g of $(workflow.item).find('svg .node.default')) {
            let id = g.getAttribute('id')
            let parts = id.split('-');
            if (parts[1]=='root_start') {
               workflow.graph.start = {"element" : g}
            } else if (parts[1]=='root_end'){
               workflow.graph.end = {"element" : g}
            }
         }
         self.updateGraphForWorkflow(workflow);
      },100);
   }

   updateGraphForWorkflow(workflow) {
      let tasks = workflow.definition[1]
      for (let [timestamp,S] of workflow.S) {
         for (let index in S) {
            let task = tasks[index]
            let node = workflow.graph.tasks[task[1].name]
            let dt = new Date(timestamp)
            if (S[index]>0 && index==0) {
               workflow.started = dt
            } else if (S[index]<0 && index==(S.length-1)) {
               workflow.ended = dt
            }
            if (node==null) {
               continue;
            }
            if (S[index]>0) {
               if (task[0]=="InvokeTask") {
                  node.element.classList.add("started")
               }
               node.started = dt
            } else if (S[index]<0) {
               if (task[0]=="InvokeTask") {
                  node.element.classList.remove("started")
                  node.element.classList.add("ended")
               }
               node.ended = dt
            }
         }
      }
      for (let name in workflow.graph.tasks) {
         let node = workflow.graph.tasks[name];
         if (node.started && node.ended) {
            node.element.setAttribute("uk-tooltip",`title: ${node.started.toISOString()} to ${node.ended.toISOString()} `)
         } else if (node.started) {
            node.element.setAttribute("uk-tooltip",`title: ${node.started.toISOString()}`)
         } else if (node.ended) {
            node.element.setAttribute("uk-tooltip",`title: ? to ${node.ended.toISOString()} `)
         }
      }
      if (workflow.started) {
         workflow.graph.start.element.setAttribute("uk-tooltip",`title: ${workflow.started.toISOString()}`)
      }
      if (workflow.ended) {
         workflow.graph.end.element.setAttribute("uk-tooltip",`title: ${workflow.ended.toISOString()}`)
      }
   }

   showWorkflowNode(workflow,node) {
      console.log(node);
   }

   showWorkflowTaskDetails(workflow) {
      if (workflow.states_shown) {
         return
      }
      let content = $(workflow.item).find(".uk-accordion-content");
      let table = $('<table class="uk-table uk-table-striped"><caption>State Information</caption><thead></thead><tbody><tbody></table>').appendTo(content);
      let head = $(table).find('thead')[0]
      $("<tr><th>Index</th><th>Name</th><th>Type</th><th>Started</th><th>Ended</th></tr>").appendTo(head)
      let body = $(table).find('tbody')[0]
      workflow.states_shown = true;
      let rows = [];
      for (let item of workflow.definition[1]) {
         let name = ""
         if (item[0]=='InvokeTask') {
            name = item[1].name
         }
         let row = $(`<tr><td>${item[1].index}</td><td>${name}</td><td>${item[0]}</td><td class='started'></td><td class='ended'></td></tr>`).appendTo(table);
         rows.push(row)
      }
      for (let [timestamp,S] of workflow.S) {
         for (let index in S) {
            let row = rows[index]
            let dt = new Date(timestamp)
            if (S[index]>0) {
               $(row).find('.started').empty().text(dt.toISOString())
               $(row).addClass('started')
            } else if (S[index]<0) {
               $(row).find('.ended').empty().text(dt.toISOString());
               $(row).removeClass('started');
               $(row).addClass('ended');
            }
         }
      }

   }

   terminateWorkflow(workflow) {
      fetch(`service/workflows/${workflow.id}/terminate`)
       .then(response => this.responseFilter(response))
       .then(data => {
          workflow.loaded = false;
          workflow.shown = false;
          this.showWorkflowDetails(workflow);
       })
       .catch(error => {
          console.log(error);
       })
   }

   deleteWorkflow(workflow) {
      fetch(`service/workflows/${workflow.id}`,{method:'DELETE'})
       .then(response => this.responseFilter(response))
       .then(data => {
          delete this.workflows[workflow.id]
          $(workflow.item).remove();
       })
       .catch(error => {
          console.log(error);
       })
   }

   fetchWorkflowDetails(workflow,callback) {
      fetch(`service/workflows/${workflow.id}`)
       .then(response => this.responseFilter(response))
       .then(data => {
          workflow.definition = data
          setTimeout(callback,1)
       })
       .catch(error => {
          console.log(error);
       })
   }
   fetchWorkflowGraph(workflow,callback) {
      fetch(`service/workflows/${workflow.id}/graph`)
       .then(response => response.text())
       .then(data => {
          workflow.graph = { 'mermaid' : data, 'tasks' : {} }
          setTimeout(callback,1)
       })
       .catch(error => {
          console.log(error);
       })
   }
   fetchWorkflowTrace(workflow,callback) {
      fetch(`service/workflows/${workflow.id}/trace/S`)
       .then(response => this.responseFilter(response))
       .then(data => {
          workflow.S = data
          setTimeout(callback,1)
       })
       .catch(error => {
          console.log(error);
       })
   }
   fetchWorkflowStatus(workflow,callback) {
      fetch(`service/workflows/${workflow.id}/state`)
       .then(response => this.responseFilter(response))
       .then(data => {
          workflow.state = data.state
          setTimeout(callback,1)
       })
       .catch(error => {
          console.log(error);
       })
   }

}

app = new App()

UIkit.util.ready(function() { app.init(); })
