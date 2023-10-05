function waitForElement(selector) {
   return new Promise(resolve => {
      if (document.querySelector(selector)) {
         return resolve(document.querySelector(selector));
      }

      const observer = new MutationObserver(mutations => {
         if (document.querySelector(selector)) {
            resolve(document.querySelector(selector));
            observer.disconnect();
         }
      });

      observer.observe(document.body, {
         childList: true,
         subtree: true
      });
   });
}

class App {
   constructor() {
      this.workflows = {}
      this.page = 0
      this.pageSize = 50
   }
   init() {
      if ($("#workflows").length>0) {
         this.initWorkflowsView();
      } else if ($("#workflow").length>0) {
         this.initWorkflowView()
      }
   }
   initWorkflowsView() {
      for (let link of $("#main-nav a")) {
         let href = $(link).attr('href');
         if (href=='#refresh') {
            $(link).click(() => {
               $("#workflows").empty();
               this.workflows = {}
               // TODO: add pagination
               this.fetchWorkflows(this.page*this.pageSize,this.pageSize);
            });
         } else if (href=='#restore') {
            $(link).click(() => {
               UIkit.modal.prompt('Restore workflow from S3 URI:', 's3://yourbucket/path').then((uri) => {
                  if (uri!=null) {
                     this.restoreWorkflow(uri)
                  }
               });
            });
         } else if (href=='#run') {

            $(link).click(() => {
               let html =
               '<form id="run" class="uk-form-stacked">' +
               '<div class="uk-modal-body">' +
               '<label for="upload-workflow">Select a workflow to start</label><input class="uk-input" id="upload-workflow" type="file">' +
               '</div>' +
               '<div class="uk-modal-footer uk-text-right">' +
               '<button class="uk-button uk-button-default uk-modal-close" type="button">Close</button>' +
               '<button class="uk-button uk-button-primary">Start</button>' +
               '</div>' +
               '</form>'
               var dialog = UIkit.modal.dialog(html,{ bgClose: false, escClose: true});
               UIkit.util.on(dialog.$el,'submit','form',(e) => {
                  e.preventDefault();
                  let file = $(dialog.$el).find('input')[0].files[0]
                  if (file==undefined) {
                     $(dialog.$el).find('label').text('No selection - select a workflow to start')
                     return;
                  }
                  dialog.hide();
                  console.log(`Upload ${file.name}`);
                  this.uploadWorkflow(file);
               });
            });
         } else if (href=='#previous-page') {
            $(link).click(() => {
               console.log('Previous page')
               if (this.page>0) {
                  $("#workflows").empty();
                  this.workflows = {}
                  this.page -= 1;
                  this.fetchWorkflows(this.page*this.pageSize,this.pageSize);
                  $("#page").text(`${this.page+1}`)

               }
            });
         } else if (href=='#next-page') {
            $(link).click(() => {
               if (Object.keys(this.workflows).length==this.pageSize) {
                  console.log('Next page')
                  $("#workflows").empty();
                  this.workflows = {}
                  this.page += 1;
                  this.fetchWorkflows(this.page*this.pageSize,this.pageSize);
                  $("#page").text(`${this.page+1}`)
               }
            });
         }

      }
      // TODO: add pagination
      this.fetchWorkflows(this.page*this.pageSize,this.pageSize);
   }

   initWorkflowView() {
      console.log("Initializing workflow view")
      console.log(window.location.search)
      let params = new URLSearchParams(window.location.search)
      let workflow_id = params.get("id")
      if (!workflow_id) {
         UIkit.notification("The id parameter was not specified.", {status:'warning'})
         return
      }
      workflow = {
         id : workflow_id,
         status: 'UNKNOWN',
         loaded: false,
         item: $("#workflow")[0],
         orientation: 'horizontal'
      }
      this.workflows[workflow.id] = workflow
      $("#workflow-id").text(workflow.id)
      this.showWorkflowDetails(workflow,"#workflow-content","#workflow-state")
   }

   _mangle(name) {
      return name==undefined ? name : name.replaceAll(":","_COLON_").replaceAll("-","_HYPHEN_")
   }

   responseFilter(response) {
      if (response.status==401) {
         // Setup auth
         //setTimeout(() => { this.relogin(); },10);
         return null
      } else if (!response.ok) {
         let err = new Error("HTTP error: "+ response.status)
         err.response = response
         err.status = response.status
         throw err
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
         workflow.orientation = 'horizontal'
         this.addWorkflow(workflow,true)
      }
   }

   addWorkflow(workflow,append) {
      console.log(`Adding ${workflow.id} ${workflow.state}`)
      let exists = this.workflows[workflow.id] != null;
      this.workflows[workflow.id] = workflow
      if (exists) {
         return;
      }
      let item = $(`<li><a class="copy" href="#copy" uk-icon="icon: copy" title="copy workflow id"></a><a class="open" href="#open" uk-icon="icon: push" title="open workflow in new window"></a><a class="expand uk-accordion-title" href="#"><span class="uk-width-expand" uk-leader>${workflow.id}</span><span class='state'>${workflow.state}</span></a><div class="uk-accordion-content"><div uk-spinner></div></div></li>`);
      if (append) {
         $(item).appendTo("#workflows")
      } else {
         $(item).prependTo("#workflows")
      }
      workflow.item = item;
      workflow.loaded = false;
      workflow.shown = false;
      workflow.states_shown = false
      $(item)
        .find("a.expand")
        .on("click",() => {
           this.showWorkflowDetails(workflow,".uk-accordion-content",".state")
        });
      $(item)
        .find("a.expand")
        .on("dblclick",() => {
           navigator.clipboard.writeText(workflow.id).then(() => {
             UIkit.notification("<span uk-icon='icon: check'></span> Copied workflow id");
           });
        });
      $(item)
        .find("a.copy")
        .on("click",() => {
           navigator.clipboard.writeText(workflow.id).then(() => {
            UIkit.notification("<span uk-icon='icon: check'></span> Copied workflow id");
         });
        });
      $(item)
        .find("a.open")
        .on("click",() => {
           window.open(`/workflow?id=${workflow.id}`,workflow.id)
        });
   }

   showWorkflowDetails(workflow,findContent,findState) {
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
                           this.fetchWorkflowStatus(
                              workflow,
                              () => {
                                 workflow.loaded = true
                                 this.showWorkflowDetails(workflow,findContent,findState)
                              }
                           );
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
      console.log(`Loaded ${workflow.id} ${workflow.state}`)
      $(workflow.item).find(findState).empty().text(workflow.state);
      $(workflow.item).find(findContent).empty();
      let content = $(workflow.item).find(findContent);
      let nav_html = '<ul class="uk-iconnav">'
      let icons = [["info","show states"],["refresh","refresh workflow"],[workflow.orientation=='horizontal' ? "arrow-down" : "arrow-right","change orientation","orientation"],["download","download workflow state"],["copy","copy workflow state"]]
      if (workflow.state=='TERMINATED' || workflow.state=='FAILED') {
         icons.push(["play","resume workflow"]);
         icons.push(["trash","delete workflow"]);
      } else if (workflow.state=='TERMINATING') {
         icons.push(["ban","stop workflow"]);
      } else if (workflow.state=='RUNNING') {
         icons.push(["ban","stop workflow"]);
      } else if (workflow.state=='FINISHED') {
         icons.push(["trash","delete workflow"]);
      }
      for (let [icon,title,href] of icons) {
         if (href==undefined) {
            href = icon
         }
         nav_html += `<li><a href="#${href}" uk-icon="icon: ${icon}" title="${title}"></a></li>`
      }
      nav_html += "</ul>";
      let nav = $(nav_html).appendTo(content);

      let diagram_id = `diagram-${workflow.id}`
      $(`<div id="${diagram_id}" class="mermaid ${workflow.orientation}"></div>`).appendTo(content);
      //mermaid.init({}, $(workflow.item).find(".uk-accordion-content .mermaid"));
      workflow.shown = true;
      // TODO: need a callback from above
      let self = this;
      for (let link of $(nav).find('a')) {
         let href = $(link).attr('href');
         if (href=='#download') {
            $(link).attr('href',`service/workflows/${workflow.id}/archive`)
            $(link).attr('target',`${workflow.id}.json`)
         } else if (href=='#refresh') {
            $(link).click(() => {
               workflow.loaded = false;
               workflow.shown = false;
               this.showWorkflowDetails(workflow,findContent,findState);
            });
         } else if (href=='#info') {
            $(link).click(() => {
               if (workflow.states_shown) {
                  $(content).find("table").remove();
                  workflow.states_shown = false
                  $(link).attr("title","show states")
               } else {
                  this.showWorkflowTaskDetails(workflow,findContent);
                  $(link).attr("title","hide states")
               }
            });
         } else if (href=='#orientation') {
            $(link).click(() => {
               if (workflow.orientation=='horizontal') {
                  workflow.orientation = 'vertical';
                  $(link).attr("uk-icon","icon: arrow-right")
               } else {
                  workflow.orientation = 'horizontal';
                  $(link).attr("uk-icon","icon: arrow-down")
               }
               workflow.loaded = false;
               workflow.shown = false;
               this.showWorkflowDetails(workflow,findContent,findState);
            });
         } else if (href=='#play') {
            $(link).click(() => {
               UIkit.modal.confirm(`Are you sure you want to restart workflow ${workflow.id}`).then(() => {
                  this.restartWorkflow(workflow,findContent,findState);
               });
            });
         } else if (href=='#copy') {
            $(link).click(() => {
               UIkit.modal.prompt('Archive workflow to S3 URI:', 's3://yourbucket/path').then((uri) => {
                  if (uri!=null) {
                     this.archiveWorkflow(workflow,uri)
                  }
               });
            });
         } else if (href=='#ban') {
            $(link).click(() => {
               UIkit.modal.confirm(`Are you sure you want to stop workflow ${workflow.id}`).then(() => {
                  this.terminateWorkflow(workflow,findContent,findState);
               });
            });
         } else if (href=='#trash') {
            $(link).click(() => {
               UIkit.modal.confirm(`Are you sure you want to delete workflow ${workflow.id}`).then(() => {
                  this.deleteWorkflow(workflow);
               });
            });
         }
      }
      if (workflow.states_shown) {
         workflow.states_shown = false
         this.showWorkflowTaskDetails(workflow,findContent);
      }
      Promise.resolve(waitForElement(`#${diagram_id}`)).then( async (diagram) => {
         console.log(diagram.parentNode);
         const { svg } = await mermaid.render(`render-${diagram_id}`, workflow.graph.mermaid);
         diagram.innerHTML = svg
         for (let g of $(workflow.item).find('svg .statediagram-state')) {
            let id = g.getAttribute('id')
            let parts = id.split('-');

            // Note: This is a bug in mermaid
            if (parts[1].startsWith('</join>')) {
               g.remove();
               continue;
            }
            let [name,index] = parts[1].split(".")
            let node =  {"element" : g, "name":name,"id":id, "index": parseInt(index)}
            workflow.graph.tasks[parts[1]] = node
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
         workflow.svg = $(workflow.item).find('.mermaid svg')[0];
         console.log(workflow.svg)
         workflow.svgContainer = $(workflow.item).find('.mermaid')[0];
         //This is because UIkit messes with the size
         setTimeout(() => {
            $(workflow.svg).removeAttr('height')
            $(workflow.svg).removeAttr('style')
            workflow.zoomer = svgPanZoom(workflow.svg, {
            zoomEnabled: true,
            panEnabled: true,
            dblClickZoomEnabled: true,
            mouseWheelZoomEnabled: true,
            controlIconsEnabled: true,
            fit: true,
            center: true,
            contain: true
            });
         },10);
      },100).catch(
         error => console.log(error)
      );
   }

   updateGraphForWorkflow(workflow) {
      let tasks = workflow.definition.T
      for (let [timestamp,S] of workflow.S) {
         for (let index in S) {
            let task = tasks[index]
            let node = workflow.graph.tasks[`${this._mangle(task[1].name)}.${index}`]
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
      if (workflow.failures!=undefined) {
         for (let index in workflow.failures) {
            if (workflow.failures[index]>0) {
               let task = tasks[index]
               let node = workflow.graph.tasks[`${this._mangle(task[1].name)}.${index}`]
               if (node==undefined) {
                  console.log(`Cannot find node for failure ${index} ${task[0]} ${this._mangle(task[1].name)}`)
                  console.log(task[1])
                  console.log(workflow.graph.tasks)
               }
               node.element.classList.remove("started")
               node.element.classList.remove("ended")
               node.element.classList.add("failed")
            }
         }
      }
   }

   showWorkflowNode(workflow,node) {
      //console.log(node);
   }

   showWorkflowTaskDetails(workflow,findContent) {
      if (workflow.states_shown) {
         return
      }
      let content = $(workflow.item).find(findContent);
      let table = $('<table class="uk-table uk-table-striped"><thead></thead><tbody><tbody></table>').appendTo(content);
      let head = $(table).find('thead')[0]
      $("<tr><th>Index</th><th>Name</th><th>Base</th><th>Type</th><th>Started</th><th>Ended</th><th>Output</th></tr>").appendTo(head)
      let body = $(table).find('tbody')[0]
      workflow.states_shown = true;
      let rows = [];
      for (let item of workflow.definition.T) {
         let name = ""
         let base = ""
         if (item[0]=='InvokeTask') {
            name = item[1].name + "("
            base = item[1].base!=undefined ? item[1].base : ""
            if (item[1].parameters!={}) {
               for (const [parameter, value] of Object.entries(item[1].parameters)) {
                  name += '<br/>'
                  name += `<span class='parameter'>${parameter} = ${value}</span>`
               }
               name += '<br/>'
            }
            name += ")"
         }
         let output = JSON.stringify(workflow.output[item[1].index]).replaceAll("'","&apos;")
         let row = $(`<tr><td>${item[1].index}</td><td>${name}</td><td>${base}</td><td>${item[0]}</td><td class='started'></td><td class='ended'></td><td><span uk-tooltip='title: ${output}'>view</span></td></tr>`).appendTo(table);
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
            if (workflow.failures!=undefined && workflow.failures[index]>0) {
               $(row).removeClass('started');
               $(row).removeClass('ended');
               $(row).addClass('failed');
               $(row).find('.ended').empty().text('FAILED');
            }
         }
      }

   }

   uploadWorkflow(file) {
      let form = new FormData()
      form.append('workflow',file)
      fetch(`service/workflows/start/upload`,{method: "POST", body: form})
       .then(response => this.responseFilter(response))
       .then(data => {
          let workflow = {id: data.workflow, orientation:'horizontal'}
          this.fetchWorkflowStatus(workflow,() => {
             this.addWorkflow(workflow,false)
          });
       })
       .catch(error => {
          if (error.status==400) {
             error.response.json().then(data => {
                UIkit.modal.alert(`Cannot upload workflow due to: ${data.message}`);
             });
          } else {
             console.log(error);
          }
       })
   }

   archiveWorkflow(workflow,uri) {
      let data = { uri: uri };
      fetch(`service/workflows/${workflow.id}/archive`,{method:'POST',body:JSON.stringify(data),headers: {'Content-Type': 'application/json'}})
       .then(response => this.responseFilter(response))
       .then(data => {
          console.log(data);
          UIkit.modal.alert(`Workflow ${workflow.id} archived to ${uri}`);
       })
       .catch(error => {
          if (error.status==400) {
             error.response.json().then(data => {
                UIkit.modal.alert(`Cannot archive workflow ${workflow.id} archived to ${uri}\n due to: ${data.message}`);
             });
          } else {
             console.log(error);
          }
       })
   }

   restoreWorkflow(uri) {
      let data = { uri: uri };
      fetch(`service/workflows/restore`,{method:'POST',body:JSON.stringify(data),headers: {'Content-Type': 'application/json'}})
       .then(response => this.responseFilter(response))
       .then(data => {
          let workflow = {id: data.workflow, orientation:'horizontal'}
          this.fetchWorkflowStatus(workflow,() => {
             this.addWorkflow(workflow,false)
          });
       })
       .catch(error => {
          if (error.status==400) {
             error.response.json().then(data => {
                UIkit.modal.alert(`Cannot restore workflow from ${uri}\n due to: ${data.message}`);
             });
          } else {
             console.log(error);
          }
       })
   }

   restartWorkflow(workflow,findContent,findState) {
      fetch(`service/workflows/${workflow.id}/restart`)
       .then(response => this.responseFilter(response))
       .then(data => {
          workflow.loaded = false;
          workflow.shown = false;
          setTimeout( () => {
             this.showWorkflowDetails(workflow,findContent,findState);
          },250);
       })
       .catch(error => {
          if (error.status==400) {
             error.response.json().then(data => {
                UIkit.modal.alert(`Cannot restart workflow ${workflow.id} due to: ${data.message}`);
             });
          } else {
             console.log(error);
          }
       })
   }

   terminateWorkflow(workflow,findContent,findState) {
      fetch(`service/workflows/${workflow.id}/terminate`,{method:'POST',body:JSON.stringify({}),headers: {'Content-Type': 'application/json'}})
       .then(response => this.responseFilter(response))
       .then(data => {
          workflow.loaded = false;
          workflow.shown = false;
          setTimeout( () => {
             this.showWorkflowDetails(workflow,findContent,findState);
          },250);
       })
       .catch(error => {
          if (error.status==400) {
             error.response.json().then(data => {
                UIkit.modal.alert(`Cannot terminate workflow ${workflow.id} due to: ${data.message}`);
             });
          } else {
             console.log(error);
          }
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
          if (error.status==400) {
             error.response.json().then(data => {
                UIkit.modal.alert(`Cannot delete workflow ${workflow.id} due to: ${data.message}`);
             });
          } else {
             console.log(error);
          }
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
      fetch(`service/workflows/${workflow.id}/graph?orientation=${workflow.orientation}`)
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
          workflow.failures = data.failures
          workflow.output = data.output
          setTimeout(callback,1)
       })
       .catch(error => {
          console.log(error);
       })
   }

}

app = new App()

UIkit.util.ready(function() { app.init(); })
