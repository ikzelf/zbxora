-- run in sqlplus
set sqlformat ansiconsole
set veri off
set lines 200
alter session set current_schema = &zabbix_schema;

col maxv new_value vid noprint
col maxm new_value mid noprint

SELECT MAX(valuemapid) AS maxv FROM valuemaps;
SELECT MAX(mappingid) AS maxm FROM mappings;

insert into valuemaps (valuemapid,name) VALUES (&vid+1, 'zbxora db.openstatus');
insert into valuemaps (valuemapid,name) VALUES (&vid+2, 'zbxora[connect,status]');
insert into valuemaps (valuemapid,name) VALUES (&vid+3, 'zbxora[query,,,status]');
insert into valuemaps (valuemapid,name) VALUES (&vid+4, 'zbxora[checks,status]');
insert into valuemaps (valuemapid,name) VALUES (&vid+5, 'zbxora rman status');
insert into valuemaps (valuemapid,name) VALUES (&vid+6, 'zbxora arl_dest');

INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+1, &vid+1,1 ,'MOUNTED');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+2, &vid+1,2 ,'READ ONLY');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+3, &vid+1,3 ,'READ WRITE');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+4, &vid+1,4 ,'READ ONLY WITH APPLY');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+5, &vid+1,0 ,'*unknown*');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+6, &vid+2,0 ,'OK');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+7, &vid+3,0 ,'OK');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+8, &vid+4,0 ,'OK');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+9, &vid+4,11,'unreadable');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+10,&vid+4,13,'parse error[s]');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+11,&vid+5,0 ,'COMPLETED');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+12,&vid+5,1 ,'FAILED');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+13,&vid+5,2 ,'COMPLETED WITH WARNINGS');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+14,&vid+5,3 ,'COMPLETED WITH ERRORS');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+15,&vid+5,4 ,'noinfo');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+16,&vid+5,9 ,'unk');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+17,&vid+5,5 ,'RUNNING');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+18,&vid+6,0 ,'OK');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+19,&vid+6,1 ,'DEFERRED');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+20,&vid+6,2 ,'ERROR');
INSERT INTO mappings (mappingid,valuemapid,VALUE,newvalue) values (&mid+21,&vid+6,3 ,'UNK');

select * from valuemaps where name like 'zbxora%' order by valuemapid;
select * from mappings where valuemapid in (select valuemapid from valuemaps where name like 'zbxora%')
order by valuemapid, mappingid;
